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
    excitation_scale: float = 1.0
    current_limited: bool = False
    flux_limited: bool = False


def base_flux(p):
    """Peak phase flux implied by the configured line-RMS V/Hz slope."""
    return min(p.exciter_flux_target,
               math.sqrt(2/3)*p.volts_per_hz/(2*math.pi))


def ramp(current, target, rise_rate, fall_rate, dt):
    delta=target-current
    limit=(rise_rate if delta>=0 else fall_rate)*dt
    return target if abs(delta)<=limit else current+math.copysign(limit,delta)


def step(p, state, dt, target_frequency, flux, motor_current_rms,
         aux_voltage, enabled=True):
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
    state.flux_limited=flux>.90*p.maximum_magnetic_flux
    if state.current_limited:
        wanted_scale=min(wanted_scale,(.90*p.motor_current_limit_rms/
                                      max(motor_current_rms,1e-12))**3)
    if state.flux_limited:
        wanted_scale=min(wanted_scale,(.85*p.maximum_magnetic_flux/
                                      max(flux,1e-12))**3)
    alpha=1-math.exp(-dt/p.vf_limit_response)
    state.excitation_scale+=alpha*(wanted_scale-state.excitation_scale)
    if not enabled:
        state.excitation_scale=max(0.0,state.excitation_scale-alpha)
    state.flux_target=base_flux(p)*state.excitation_scale if enabled else 0.0
    # V/f is line-line RMS.  The only low-frequency boost is measured R_s I_s;
    # there is no fixed offset.  Derating acts before converter/network solve.
    resistive_drop=math.sqrt(3)*p.stator_resistance*motor_current_rms
    requested=(p.volts_per_hz*state.frequency_command*state.excitation_scale
               +resistive_drop)
    modulation_limit=max(0.0,aux_voltage)/math.sqrt(2)
    state.voltage_command=min(requested,modulation_limit) if enabled else 0.0
    return state
