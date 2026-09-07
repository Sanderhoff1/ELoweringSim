"""Small externally supplied flux exciter, not a regenerative VFD.

Active output is bounded; negative terminal active power is restricted to a
small local dissipative allowance and 2% of contemporaneous machine export.
It is NEVER regenerated to the external supply. Reactive current gets the
remaining converter current/voltage capability. No zero-P identity is imposed.
"""
import math


def current(p, voltage, request, reference_axis, machine_export, enabled):
    if not enabled:
        return 0j,0.0,0.0,False
    amplitude=abs(voltage)
    axis=voltage/amplitude if amplitude>1e-10 else reference_axis
    desired=request/axis
    maximum=math.sqrt(2)*p.inverter_current_limit
    # The AC terminal capability comes from the 24 V battery boost stage, not
    # from an independent 400 V energy source.
    umax=math.sqrt(2/3)*p.boost_target_voltage
    resistance=p.inverter_output_resistance
    reverse=min(p.exciter_absorption_limit,0.02*max(0.0,machine_export))
    scale=1.5*max(amplitude,1e-10)
    low=max(-maximum,(-umax-amplitude)/resistance,-reverse/scale)
    high=min(maximum,(umax-amplitude)/resistance,p.exciter_active_limit/scale)
    if low>high:
        return 0j,p.inverter_idle_loss,p.inverter_idle_loss,True
    real=min(high,max(low,desired.real))
    iqmax=math.sqrt(max(0.0,min(maximum**2-real**2,
                 (umax**2-(amplitude+resistance*real)**2)/resistance**2)))
    imaginary=min(iqmax,max(-iqmax,desired.imag))
    output=axis*complex(real,imaginary)
    pac=1.5*amplitude*real
    conduction=1.5*resistance*abs(output)**2+p.inverter_idle_loss
    # Negative AC watts are dissipated locally, not silently discarded.
    loss=conduction+max(0.0,-pac)
    supply=max(0.0,pac)+conduction
    return output,supply,loss,abs(output-request)>1e-6
