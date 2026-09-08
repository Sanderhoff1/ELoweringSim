"""Signed physical ports and conservation equations, shared by UI and tests.

Every component obeys input = output + heat + storage_rate. Real power
alone enters this equation. Positive connection power follows its named path.
AC currents are balanced fundamental equivalents (peak alpha-beta / sqrt(2)).
"""
import math
from .auxiliary import paths


def component(pin=0., pout=0., heat=0., storage=0., energy=0., **details):
    return dict(input=pin, output=pout, heat=heat, storage_rate=storage,
                energy=energy, residual=pin-pout-heat-storage, **details)


def ac(v, i, equivalent=False):
    power=1.5*v*i.conjugate()
    axis=v/abs(v) if abs(v)>1e-12 else 1+0j
    current=i/axis/math.sqrt(2)
    return dict(kind='ac',voltage=math.sqrt(1.5)*abs(v),current=abs(i)/math.sqrt(2),
                active_current=current.real,reactive_current=-current.imag,
                power=power.real,reactive=power.imag,direction=sign(power.real),
                equivalent=equivalent)


def sign(x):
    return 1 if x>1e-9 else -1 if x<-1e-9 else 0


def dc(v,power):
    return dict(kind='dc',voltage=v,current=power/v if v else 0.,
                power=power,direction=sign(power))


def diagnostics(model,r):
    p,s,e,k=model.parameters,model.state,model.electrical,model.kernel
    cap=model.excitation_mode=='capacitor'
    enabled=model.excitation_active()
    rate=k.rate((e.stator_flux,e.rotor_flux,e.voltage),e.phase,model.frequency(),s.omega,e.dc_voltage,enabled,True,cap)
    v=rate.terminal
    is_,ir,_=k.currents(e.stator_flux,e.rotor_flux)
    machine=ac(v,-(is_+v*k.gc))
    exciter=ac(v,rate.exciter)
    ic=k.cac*rate.voltage if cap else 0j
    capacitor=ac(v,ic)
    ib=2*rate.rectifier*v/(3*abs(v)**2) if abs(v)>1e-12 else 0j
    bridge=ac(v,ib,True)
    aux=paths(p,e.battery_energy,rate.supply,e.dc_voltage,model.max_electrical_step,model.charger_enabled)
    shaft=-rate.torque*s.omega
    gravity=r['gravity_power']
    gear=r['gear_power']+r['drivetrain_power']+r['brake_power']+r['friction_power']
    kinetic=(p.inertia+p.mass*p.radius**2)*s.omega*r['acceleration']/p.radius
    magnetic_rate=1.5*(is_.conjugate()*rate.ps+ir.conjugate()*rate.pr).real
    magnetic,_=k.stored(e.stator_flux,e.rotor_flux,v)
    dc_heat=r['dc_brake_power']
    components={
        'load':component(0,gravity,storage=-gravity,energy=r['potential_energy']),
        'gear':component(gravity,shaft,gear,kinetic,r['kinetic_energy']),
        'machine':component(shaft,machine['power'],rate.copper+rate.core,magnetic_rate,magnetic,
                            copper=rate.copper,core=rate.core),
        'ac_bus':component(machine['power']+exciter['power'],bridge['power']+capacitor['power']),
        'capacitor':component(capacitor['power'],storage=1.5*k.cac*(v.conjugate()*rate.voltage).real if cap else 0.,energy=r['capacitor_energy']),
        'rectifier':component(rate.rectifier,rate.dc_input,rate.bridge_loss),
        'dc_link':component(rate.dc_input,dc_heat+aux['charger_input'],storage=rate.dc_input-dc_heat-aux['charger_input'],energy=e.dc_energy),
        'chopper':component(dc_heat,dc_heat),
        'resistor':component(dc_heat,heat=dc_heat),
        'exciter':component(rate.supply,exciter['power'],rate.converter_loss),
        'boost':component(aux['boost_input'],aux['boost_output'],aux['boost_heat']),
        'charger':component(aux['charger_input'],aux['charger_output'],aux['charger_heat']),
        'battery':component(aux['charger_output'],aux['boost_input'],aux['heat'],aux['storage'],e.battery_energy),
    }
    ports={
        'load_gear':dict(kind='linear',force=p.mass*p.gravity,velocity=r['velocity'],power=gravity,direction=sign(gravity)),
        'gear_machine':dict(kind='shaft',torque=-rate.torque,rpm=r['rpm'],power=shaft,direction=sign(shaft)),
        'aux_bus':ac(v,rate.exciter-ic),'machine_bus':machine,'exciter_bus':exciter,'bus_capacitor':capacitor,'bus_rectifier':bridge,
        'rectifier_dc':dc(e.dc_voltage,rate.dc_input),'dc_chopper':dc(e.dc_voltage,dc_heat),
        'chopper_resistor':dc(e.dc_voltage,dc_heat),'dc_charger':dc(e.dc_voltage,aux['charger_input']),
        'charger_battery':dc(aux['voltage'],aux['charger_output']),
        'battery_boost':dc(aux['voltage'],aux['boost_input']),
        'boost_exciter':dc(p.boost_target_voltage if enabled and rate.supply>0 else 0.,aux['boost_output']),
        'battery_terminal':dc(aux['voltage'],aux['power']),
    }
    mismatch=rate.exciter-is_-v*k.gc-ib-ic
    return dict(components=components,connections=ports,kcl=mismatch,
                reactive_residual=machine['reactive']+exciter['reactive']-bridge['reactive']-capacitor['reactive'])
