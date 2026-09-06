"""Estimated small geared hoist; not a measured motor equivalent circuit."""
from .parameters import Parameters


def small_hoist(**changes):
    # 900 W / (1420 rpm * 2 pi / 60) = 6.05 Nm rated shaft torque.
    # 0.10 m drum / 60:1 gearing gives 0.001667 m per shaft radian.
    values = dict(mass=300, crane_height=200, radius=0.1/60,
                  inertia=0.008, damping=0.001, brake_torque=10,
                  brake_response=0.2, supply_frequency=50, pole_pairs=2,
                  peak_motor_torque=15, peak_slip=0.25,
                  volts_per_hz=8, reference_volts_per_hz=8,
                  stator_resistance=7, rotor_resistance=7.35,
                  stator_leakage=0.025, rotor_leakage=0.025,
                  magnetizing_inductance=0.65, saturation_flux=1.8,
                  capacitor_capacitance=6, ac_load_resistance=220,
                  initial_flux=0.005, initial_shaft_rpm=0,
                  precharge_voltage=0)
    values.update(changes)
    return Parameters(**values)
