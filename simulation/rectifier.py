"""Averaged, one-way three-phase bridge with finite effective source resistance.

No six-pulse ripple or semiconductor switching. Power into the bridge is
exactly DC-link input plus effective bridge/source loss.
"""
import math

# E = 3 sqrt(2) / pi * V_LL,rms = K * |v_alpha_beta,phase_peak|.
K = 3*math.sqrt(3)/math.pi


def bridge(p, voltage, dc_voltage, enabled, duty=1.0):
    dc_voltage = max(0.0, float(dc_voltage.real))
    if not enabled:
        return dict(current=0.0, ac_current=0j, power=0.0,
                    dc_power=0.0, loss=0.0, brake_power=0.0, derivative=0.0)
    magnitude = abs(voltage)
    emf = K*magnitude
    current = max(0.0, (emf-dc_voltage)/p.rectifier_resistance)
    power = emf*current
    ac_current = (2*K*current/3)*(voltage/magnitude) if magnitude else 0j
    brake_current = min(1.0,max(0.0,duty))*dc_voltage/p.dc_brake_resistance
    return dict(current=current, ac_current=ac_current, power=power,
                dc_power=dc_voltage*current,
                loss=current**2*p.rectifier_resistance,
                brake_power=dc_voltage*brake_current,
                derivative=(current-brake_current)/(p.dc_capacitance*1e-6))
