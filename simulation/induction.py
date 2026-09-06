"""Phase 2: steady-state, symmetric Kloss torque-slip approximation.

Phase 3 optionally adds ideal V/f voltage and a linear magnetizing branch.
No stator/core losses, flux states or leakage reactive power are represented.
Positive torque drives lowering; positive exported power goes to the AC sink.
"""
import math
from .parameters import Parameters
from .excitation import excitation_readings


def motor_readings(parameters: Parameters, omega: float, connected: bool,
                   ideal_excitation=False, inverter_enabled=True, capacitors_enabled=False):
    p = parameters
    synchronous_omega = 2*math.pi*p.supply_frequency/p.pole_pairs
    slip = (synchronous_omega-omega)/synchronous_omega
    ratio = slip/p.peak_slip
    excitation = excitation_readings(p, connected and inverter_enabled, capacitors_enabled) if ideal_excitation else {}
    flux_scale = excitation['excitation_flux_ratio']**2 if ideal_excitation else 1.0
    peak_torque = p.peak_motor_torque*flux_scale
    torque = 2*peak_torque*ratio/(1+ratio*ratio) if connected else 0.0
    # Air-gap input equals ideal terminal input when stator/core losses are zero.
    electrical_input = torque*synchronous_omega
    shaft_power = torque*omega
    rotor_loss = torque*(synchronous_omega-omega)
    if not connected:
        mode = "DISCONNECTED"
    elif ideal_excitation and excitation['line_voltage'] == 0:
        mode = "UNEXCITED"
    elif abs(slip) < 1e-9 or peak_torque == 0:
        mode = "NO TORQUE"
    elif slip < 0:
        mode = "GENERATING"
    else:
        mode = "MOTORING" if omega > 0 else "STALLED / ENERGIZED"
    if ideal_excitation:
        voltage = excitation['line_voltage']
        active_current = electrical_input/(math.sqrt(3)*voltage) if voltage else 0.0
        excitation.update(machine_line_current=math.hypot(active_current, excitation['magnetizing_current']),
                          active_boundary_current=active_current,
                          machine_apparent_power=math.hypot(electrical_input, excitation['machine_reactive_demand']))
    return dict(synchronous_omega=synchronous_omega,
                synchronous_rpm=synchronous_omega*60/(2*math.pi),
                slip=slip, motor_torque=torque, motor_shaft_power=shaft_power,
                electrical_input=electrical_input, electrical_export=-electrical_input,
                rotor_loss=rotor_loss, motor_mode=mode,
                effective_peak_torque=peak_torque if connected else 0.0,
                beyond_peak=connected and peak_torque>0 and abs(slip)>p.peak_slip,
                **excitation)
