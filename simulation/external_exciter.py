"""Reverse-blocking averaged flux exciter supplied by the auxiliary DC link.

The virtual output impedance shapes the current command and voltage capability;
only the explicit conduction resistance and idle loss become physical heat.
The AC active-current component is constrained to be nonnegative, so generated
real power can never enter the inverter.  Reactive current remains bidirectional.
"""
import math


def current(p, voltage, request, reference_axis, machine_export, enabled,
            supply_limit=float('inf'), dc_voltage=None, active_limit=None):
    if not enabled or supply_limit < p.inverter_idle_loss:
        return 0j,0.0,0.0,False
    amplitude=abs(voltage)
    axis=voltage/amplitude if amplitude>1e-10 else reference_axis
    desired=request/axis
    maximum=math.sqrt(2)*p.inverter_current_limit
    reactive_max=math.sqrt(2)*p.inverter_reactive_current_limit
    # The instantaneous modulation ceiling comes from the finite auxiliary
    # capacitor, not directly from the boost target setting.
    umax=max(0.0,p.boost_target_voltage if dc_voltage is None else dc_voltage)/math.sqrt(3)
    resistance=p.inverter_output_resistance  # virtual/control impedance
    active_limit=p.exciter_active_limit if active_limit is None else max(0.0,active_limit)
    scale=1.5*max(amplitude,1e-10)
    low=0.0
    high=min(maximum,(umax-amplitude)/resistance,active_limit/scale)
    if low>high:
        return 0j,p.inverter_idle_loss,p.inverter_idle_loss,True
    real=min(high,max(low,desired.real))
    iqmax=min(reactive_max,math.sqrt(max(0.0,min(maximum**2-real**2,
                (umax**2-(amplitude+resistance*real)**2)/resistance**2))))
    imaginary=min(iqmax,max(-iqmax,desired.imag))
    output=axis*complex(real,imaginary)
    # Limit BEFORE the network solve, including idle and conduction losses.
    if supply_limit < p.inverter_idle_loss:
        return 0j,0.,0.,True
    a=1.5*p.inverter_conduction_resistance*abs(output)**2
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
    conduction=1.5*p.inverter_conduction_resistance*abs(output)**2+p.inverter_idle_loss
    loss=conduction
    supply=pac+conduction
    return output,supply,loss,abs(output-request)>1e-6
