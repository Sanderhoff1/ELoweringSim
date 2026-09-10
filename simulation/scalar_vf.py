"""Embedded-style scalar V/f command generator for the exciter mode.

This controller never changes plant state directly.  It produces a frequency,
flux and voltage request for the already current/voltage/power-limited exciter.
"""
from dataclasses import dataclass
import math


@dataclass
class ScalarVFState:
    frequency_command: float = 0.0
    voltage_command: float = 0.0
    flux_target: float = 0.0
    flux_error: float = 0.0
    flux_integral: float = 0.0
    base_voltage_command: float = 0.0
    resistive_compensation: float = 0.0
    flux_correction: float = 0.0
    unlimited_voltage_command: float = 0.0
    excitation_scale: float = 1.0
    current_limited: bool = False
    flux_limited: bool = False
    voltage_limited: bool = False


def base_flux(p):
    """Peak phase flux implied by the configured line-RMS V/Hz slope."""
    return min(p.exciter_flux_target,
               math.sqrt(2/3)*p.volts_per_hz/(2*math.pi))


def ramp(current, target, rise_rate, fall_rate, dt):
    delta=target-current
    limit=(rise_rate if delta>=0 else fall_rate)*dt
    return target if abs(delta)<=limit else current+math.copysign(limit,delta)


def base_voltage(p, frequency):
    """Line-RMS air-gap EMF consistent with ``base_flux``."""
    return math.sqrt(3/2)*2*math.pi*max(0.0, frequency)*base_flux(p)


def stator_drop_compensation(p, stator_current_peak, flux_vector,
                             controller_phase=0.0):
    """Signed line-RMS Rs drop along the induced-voltage axis.

    ``stator_current_peak`` is the stationary-frame winding-current vector, not
    its magnitude and not the terminal core-loss current.  Positive projection
    raises voltage in motoring, negative projection lowers it in generating,
    and ideal magnetizing current contributes zero because it is in quadrature.
    """
    flux_axis=(flux_vector/abs(flux_vector) if abs(flux_vector)>1e-12
               else complex(math.cos(controller_phase),math.sin(controller_phase)))
    voltage_axis=1j*flux_axis
    current_projection=(stator_current_peak*voltage_axis.conjugate()).real
    return math.sqrt(3/2)*p.stator_resistance*current_projection


def _clamp(value, bound):
    return min(bound,max(-bound,value))


def step(p, state, dt, target_frequency, flux, motor_current_rms,
         aux_voltage, enabled=True, stator_current_peak=0j, flux_vector=0j,
         controller_phase=0.0):
    """Advance commands using measurements available to a scalar controller.

    Current and flux limiting reduce the excitation request before the network
    solve.  The plant's converter current/modulation limits then enforce the
    request physically; no measured result is cosmetically clipped.
    """
    target=max(0.0,float(target_frequency)) if enabled else 0.0
    if 0.0<target<p.minimum_control_frequency:
        target=p.minimum_control_frequency
    state.frequency_command=ramp(
        state.frequency_command,target,p.frequency_accel_rate,
        p.frequency_decel_rate,dt)
    wanted_scale=1.0
    state.current_limited=motor_current_rms>.95*p.motor_current_limit_rms
    # Normal target tracking is handled by the PI regulator below.  This flag
    # is reserved for the separate protection-region derating.
    state.flux_limited=flux>.95*p.maximum_magnetic_flux
    if state.current_limited:
        wanted_scale=min(wanted_scale,(.90*p.motor_current_limit_rms/
                                      max(motor_current_rms,1e-12))**3)
    if state.flux_limited:
        wanted_scale=min(wanted_scale,(.90*p.maximum_magnetic_flux/
                                      max(flux,1e-12))**3)
    alpha=1-math.exp(-dt/p.vf_limit_response)
    state.excitation_scale+=alpha*(wanted_scale-state.excitation_scale)
    if not enabled:
        state.excitation_scale=max(0.0,state.excitation_scale-alpha)
    state.flux_target=base_flux(p) if enabled else 0.0
    state.flux_error=state.flux_target-flux if enabled else 0.0
    state.base_voltage_command=base_voltage(p,state.frequency_command) if enabled else 0.0
    state.resistive_compensation=(stator_drop_compensation(
        p,stator_current_peak,flux_vector,controller_phase) if enabled else 0.0)
    if enabled:
        candidate=state.flux_integral+state.flux_error*dt
        correction=_clamp(p.vf_flux_kp*state.flux_error+p.vf_flux_ki*candidate,
                          p.vf_flux_correction_limit)
        state.flux_integral=((correction-p.vf_flux_kp*state.flux_error)/p.vf_flux_ki
                             if p.vf_flux_ki>0 else 0.0)
        state.flux_correction=correction
    else:
        state.flux_integral=0.0
        state.flux_correction=0.0
    requested=max(0.0,state.base_voltage_command+state.resistive_compensation+
                  state.flux_correction)
    state.unlimited_voltage_command=requested
    modulation_limit=max(0.0,aux_voltage)/math.sqrt(2)
    limited_request=requested*state.excitation_scale
    state.voltage_command=min(limited_request,modulation_limit) if enabled else 0.0
    state.voltage_limited=(enabled and state.voltage_command<requested-1e-9)
    # Conditional integration prevents current/protection/modulation limits from
    # winding the normal flux loop farther into saturation.
    if state.voltage_limited and state.flux_error>0 and p.vf_flux_ki>0:
        state.flux_integral-=state.flux_error*dt
        state.flux_correction=_clamp(
            p.vf_flux_kp*state.flux_error+p.vf_flux_ki*state.flux_integral,
            p.vf_flux_correction_limit)
        requested=max(0.0,state.base_voltage_command+
                      state.resistive_compensation+state.flux_correction)
        state.unlimited_voltage_command=requested
        state.voltage_command=min(requested*state.excitation_scale,
                                  modulation_limit)
        state.voltage_limited=state.voltage_command<requested-1e-9
    return state
