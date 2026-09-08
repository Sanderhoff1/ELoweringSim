"""Small battery/boost supplied flux exciter, not a regenerative VFD.

Active output is bounded; negative terminal active power is restricted to a
small local dissipative allowance and 2% of contemporaneous machine export.
It is never regenerated through the nonregenerative boost stage. Reactive current gets the
remaining converter current/voltage capability. No zero-P identity is imposed.
"""
import math


def current(p, voltage, request, reference_axis, machine_export, enabled, supply_limit=float('inf')):
    if not enabled or supply_limit < p.inverter_idle_loss:
        return 0j,0.0,0.0,False
    amplitude=abs(voltage)
    axis=voltage/amplitude if amplitude>1e-10 else reference_axis
    desired=request/axis
    maximum=math.sqrt(2)*p.inverter_current_limit
    # The AC terminal capability comes from the 24 V battery boost stage, not
    # from an independent 400 V energy source.
    umax=p.boost_target_voltage/math.sqrt(3)
    resistance=p.inverter_output_resistance
    reverse=min(p.exciter_absorption_limit,0.02*max(0.0,machine_export))
    scale=1.5*max(amplitude,1e-10)
    low=max(-maximum,(-umax-amplitude)/resistance,-reverse/scale)
    high=min(maximum,(umax-amplitude)/resistance,p.exciter_active_limit/scale)
    if low>high:
        return 0j,p.inverter_idle_loss,p.inverter_idle_loss,True
    real=min(high,max(low,desired.real))
    iqmax=math.sqrt(max(0.0,min(maximum**2-real**2,(umax**2-(amplitude+resistance*real)**2)/resistance**2)))
    imaginary=min(iqmax,max(-iqmax,desired.imag))
    output=axis*complex(real,imaginary)
    # Limit BEFORE the network solve, including idle and conduction losses.
    if supply_limit < p.inverter_idle_loss:
        return 0j,0.,0.,True
    a=1.5*resistance*abs(output)**2
    b=max(0.,1.5*(voltage*output.conjugate()).real)
    budget=supply_limit-p.inverter_idle_loss
    if a+b>budget:
        scale=2*budget/(b+math.sqrt(b*b+4*a*budget)) if budget>0 else 0.
        output*=scale
        real=(output/axis).real
    # Scaling a small absorbing current toward zero can leave the voltage
    # capability circle when the machine terminal is already above its ceiling.
    # Block instead; Kernel re-solves KCL with the resulting zero current.
    if abs(voltage+resistance*output)>umax+1e-9:
        return 0j,p.inverter_idle_loss,p.inverter_idle_loss,True
    pac=1.5*amplitude*real
    conduction=1.5*resistance*abs(output)**2+p.inverter_idle_loss
    # Negative AC watts are dissipated locally, not silently discarded.
    loss=conduction+max(0.0,-pac)
    supply=max(0.0,pac)+conduction
    return output,supply,loss,abs(output-request)>1e-6
