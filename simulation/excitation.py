"""Ideal Phase 3 V/f excitation: magnetizing branch only, no switching/DC bus.

RMS quantities are balanced three-phase; Lm is a star-equivalent phase value.
Optional Phase 4 delta capacitors share the modeled reactive demand.
The inverter supplies the remainder (or absorbs a surplus), without real loss.
A separate ideal active-power boundary supplies/absorbs the machine's real P.
"""
import math


def excitation_readings(p, enabled, capacitors_enabled=False):
    commanded_voltage = p.volts_per_hz*p.supply_frequency
    voltage = commanded_voltage if enabled else 0.0
    phase_voltage = voltage/math.sqrt(3)
    reactance = 2*math.pi*p.supply_frequency*p.magnetizing_inductance
    current = phase_voltage/reactance
    reactive_power = 3*phase_voltage*current
    angular_frequency = 2*math.pi*p.supply_frequency
    capacitance = p.capacitor_capacitance*1e-6 if capacitors_enabled else 0.0
    # Delta branch sees line-line RMS voltage; line current is sqrt(3) times
    # capacitor branch current. Positive Qc means reactive power supplied.
    capacitor_branch_current = angular_frequency*capacitance*voltage
    capacitor_supply = 3*voltage*capacitor_branch_current
    inverter_supply = reactive_power-capacitor_supply
    signed_inverter_current = inverter_supply/(math.sqrt(3)*voltage) if voltage else 0.0
    return dict(voltage_command=commanded_voltage, line_voltage=voltage,
                phase_voltage=phase_voltage, magnetizing_current=current,
                machine_reactive_demand=reactive_power,
                capacitor_reactive_supply=capacitor_supply,
                capacitor_branch_current=capacitor_branch_current,
                capacitor_line_current=math.sqrt(3)*capacitor_branch_current,
                capacitor_real_power=0.0,
                compensation_fraction=capacitor_supply/reactive_power if reactive_power else 0.0,
                matching_capacitance=1e6/(3*angular_frequency**2*p.magnetizing_inductance),
                inverter_reactive_supply=inverter_supply,
                inverter_current=abs(signed_inverter_current),
                inverter_signed_reactive_current=signed_inverter_current,
                inverter_real_power=0.0,
                inverter_apparent_power=abs(inverter_supply),
                excitation_flux_ratio=p.volts_per_hz/p.reference_volts_per_hz if enabled else 0.0)
