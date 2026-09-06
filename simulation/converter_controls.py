"""Averaged chopper control and bounded DC-fed excitation converter."""
import math


def chopper(p, voltage, duty, enabled):
    command = min(p.chopper_max_duty,max(0.0,(voltage-p.chopper_threshold)/p.chopper_band)) if enabled else 0.0
    return command, (command-duty)/p.chopper_response


def exciter(p, voltage, requested_current, dc_voltage, enabled):
    """Bound internal voltage and phase current simultaneously.

    The converter is a controlled voltage behind an effective series resistor.
    Commands are projected into the intersection of the voltage/current disks.
    If those constraints have no intersection, an ideal isolation trip blocks
    output. Uncontrolled diode paths and switching ripple are outside this model.
    """
    maximum = max(0.0,dc_voltage)/math.sqrt(3)
    result = dict(current=0j, loss=0.0, dc_power=0.0, dc_current=0.0,
                  current_limited=False, voltage_limited=False,
                  status='OFF', maximum_voltage=maximum, internal_voltage=0j)
    if not enabled:
        return result
    if dc_voltage < p.inverter_min_dc_voltage:
        result['status']='DC TOO LOW'
        return result
    resistance = p.inverter_output_resistance
    radius = resistance*math.sqrt(2)*p.inverter_current_limit
    desired = voltage+resistance*requested_current
    u = desired*min(1.0,maximum/max(abs(desired),1e-12))
    result['voltage_limited'] = abs(desired)>maximum+1e-9
    if abs(u-voltage)>radius:
        result['current_limited']=True
        if abs(voltage)>maximum+radius:
            result.update(status='AC OVERVOLTAGE BLOCK',voltage_limited=True)
            return result
        if abs(voltage)<=maximum:
            # Both endpoints are inside the voltage disk; interpolation stays in it.
            u=voltage+(u-voltage)*radius/abs(u-voltage)
        else:
            # Closest feasible voltage to the bus, then interpolate toward u.
            near=maximum*voltage/abs(voltage)
            direction=u-near
            b=2*((near-voltage).conjugate()*direction).real
            a=abs(direction)**2
            c=abs(near-voltage)**2-radius**2
            t=(-b+math.sqrt(max(0.0,b*b-4*a*c)))/(2*a) if a else 0
            u=near+min(1.0,max(0.0,t))*direction
    current=(u-voltage)/resistance
    loss=1.5*resistance*abs(current)**2+p.inverter_idle_loss
    ac_power=1.5*(voltage*current.conjugate()).real
    result.update(current=current,loss=loss,dc_power=ac_power+loss,
                  dc_current=(ac_power+loss)/dc_voltage,internal_voltage=u)
    result['status']='CURRENT + VOLTAGE LIMIT' if result['current_limited'] and result['voltage_limited'] else 'CURRENT LIMIT' if result['current_limited'] else 'VOLTAGE LIMIT' if result['voltage_limited'] else 'TRACKING'
    return result
