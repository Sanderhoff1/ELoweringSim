"""Cycle-averaged capacitor-input bridge (balanced sinusoidal AC).

Average max((V_peak*cos(theta)-Vdc)/R,0) over each 60-degree crest.
This retains blocking, partial conduction, charging loss and the sqrt(2)*V_LL
no-load limit. It does not model diode switching, harmonics or overlap inductance.
"""
import math


def transfer(line_rms, dc_voltage, resistance):
    peak=math.sqrt(2)*max(0.0,line_rms)
    if peak<=dc_voltage or peak==0:
        return 0.0,0.0,0.0
    angle=min(math.pi/6,math.acos(max(0.0,dc_voltage)/peak))
    sine=math.sin(angle)
    factor=6/(math.pi*resistance)
    current=factor*(peak*sine-dc_voltage*angle)
    ac_power=factor*(peak*peak*(angle/2+math.sin(2*angle)/4)-peak*dc_voltage*sine)
    return current,ac_power,max(0.0,ac_power-dc_voltage*current)


def midpoint_voltage(energy, capacitance, h, line_rms, resistance, load_conductance):
    """Positive discrete-gradient DC predictor, including charging from E=0.

    Solve C(V1-V0)/h = I_rect((V0+V1)/2)-G*(V0+V1)/2.
    The bracket is a root-solver bound, not a clamp on an integrated state.
    Actual energy is subsequently advanced from the integrated power balance.
    """
    if energy<0:
        raise ValueError('DC energy cannot be negative')
    v0=math.sqrt(2*energy/capacitance)
    upper=v0+h*transfer(line_rms,0,resistance)[0]/capacitance
    lower=0.0
    v1=v0
    peak=math.sqrt(2)*line_rms
    for _ in range(12):
        vm=(v0+v1)/2
        current=transfer(line_rms,vm,resistance)[0]
        f=capacitance*(v1-v0)/h-current+load_conductance*vm
        if abs(f)<1e-12:
            break
        if f>0: upper=v1
        else: lower=v1
        angle=min(math.pi/6,math.acos(vm/peak)) if peak>vm else 0.0
        slope=capacitance/h+3*angle/(math.pi*resistance)+load_conductance/2
        candidate=v1-f/slope
        v1=candidate if lower<=candidate<=upper else (lower+upper)/2
    return (v0+v1)/2
