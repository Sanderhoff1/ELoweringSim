"""Finite constant-OCV battery and isolated averaged converter power paths.

Positive current discharges: Vt=Voc-RI, Pterminal=Vt I,
chemical depletion=Voc I=Pterminal+R I². No SOC/energy clipping.
"""
import math


def discharge_limit(p, energy=float('inf'), h=1e-4):
    i=min(p.battery_discharge_current_limit, energy/(h*p.battery_voltage))
    if p.battery_internal_resistance:
        i=min(i,p.battery_voltage/(2*p.battery_internal_resistance))
    return (p.battery_voltage-p.battery_internal_resistance*i)*i


def boost_limit(p, energy=float('inf'), h=1e-4):
    return min(discharge_limit(p,energy,h)*p.boost_efficiency,
               p.boost_input_power_limit*p.boost_efficiency,
               p.boost_target_voltage*p.boost_output_current_limit)


def boost_available_current(p, voltage, energy=float('inf'), h=1e-4):
    """Averaged high-side current available at the present auxiliary voltage."""
    voltage=max(float(voltage),p.battery_voltage)
    return min(p.boost_output_current_limit,
               boost_limit(p,energy,h)/voltage)


def boost_current(p, voltage, state, energy=float('inf'), h=1e-4, enabled=True):
    """Advance the finite boost current command with its configured response."""
    available=boost_available_current(p,voltage,energy,h)
    requested=min(available,max(0.0,(p.boost_target_voltage-voltage)*p.boost_voltage_gain)) if enabled else 0.0
    next_state=requested+(max(0.0,state)-requested)*math.exp(-h/p.boost_response)
    actual=(min(available,(max(0.0,state)+next_state)/2)
            if enabled and voltage<p.boost_target_voltage else 0.0)
    return actual,next_state,available,requested


def auxiliary_step(capacitance, energy, h, source_current, load_power):
    """Energy-conserving averaged auxiliary-link capacitor update.

    Source current and inverter input power are held at their midpoint values.
    The solve is bounded at zero volts; a negative-energy request is reported
    explicitly instead of being clipped.
    """
    if energy < 0 or capacitance <= 0 or h <= 0:
        raise ValueError('Auxiliary-link energy, capacitance and step must be positive')
    v0=math.sqrt(2*energy/capacitance)
    def balance(v1):
        vm=(v0+v1)/2
        return .5*capacitance*(v1*v1-v0*v0)-h*(source_current*vm-load_power)
    if balance(0.0)>1e-12:
        raise ValueError('Auxiliary DC link cannot supply the requested inverter energy')
    # The midpoint energy equation is exactly quadratic in v1:
    # C v1^2 - h Is v1 - C v0^2 - h Is v0 + 2 h Pload = 0.
    # The old 70-step bisection converged to this nonnegative root.
    drive=h*source_current
    discriminant=drive*drive+4*capacitance*(
        capacitance*v0*v0+drive*v0-2*h*load_power)
    if discriminant < -1e-18:
        raise ValueError('Auxiliary-link solve has no finite real voltage')
    v1=(drive+math.sqrt(max(0.0,discriminant)))/(2*capacitance)
    if not math.isfinite(v1) or v1>1e6:
        raise ValueError('Auxiliary-link solve did not bracket a finite voltage')
    vm=(v0+v1)/2
    output_power=source_current*vm
    next_energy=.5*capacitance*v1*v1
    return dict(voltage=v1,midpoint_voltage=vm,energy=next_energy,
                source_power=output_power,load_power=load_power,
                capacitor_power=output_power-load_power)


def battery(p, terminal_power):
    v,r=p.battery_voltage,p.battery_internal_resistance
    i=2*terminal_power/(v+math.sqrt(max(0,v*v-4*r*terminal_power)))
    return v-r*i,i,r*i*i


def paths(p, energy, supply, vdc, h, charger_enabled=True):
    draw=supply/p.boost_efficiency
    room=max(0,p.battery_capacity_wh*3600-energy)
    charge_i=min(p.battery_charge_current_limit,room/(h*p.battery_voltage))
    max_charge=(p.battery_voltage+p.battery_internal_resistance*charge_i)*charge_i
    cin=min(p.charger_power_limit,(draw+max_charge)/p.charger_efficiency) if charger_enabled and vdc>=p.charger_min_dc_voltage else 0.
    cout=cin*p.charger_efficiency
    vt,i,heat=battery(p,draw-cout)
    return dict(boost_input=draw,boost_output=supply,boost_heat=draw-supply,
                charger_input=cin,charger_output=cout,charger_heat=cin-cout,
                voltage=vt,current=i,power=vt*i,heat=heat,storage=-p.battery_voltage*i)
