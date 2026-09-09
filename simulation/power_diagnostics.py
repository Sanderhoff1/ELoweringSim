"""Signed physical ports and conservation equations, shared by UI and tests.

Every component obeys input = output + heat + storage_rate. Real power
alone enters this equation. Positive connection power follows its named path.
AC currents are balanced fundamental equivalents (peak alpha-beta / sqrt(2)).
"""
import math
from .auxiliary import boost_current, boost_limit, paths


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
    active_limit=(p.exciter_active_limit if model.release_time is None else p.exciter_run_active_limit)
    k.supply_limit=e.aux_energy/model.max_electrical_step+boost_limit(
        p,e.battery_energy,model.max_electrical_step)
    rate=k.rate((e.stator_flux,e.rotor_flux,e.voltage),e.phase,model.frequency(),s.omega,
                e.dc_voltage,enabled,True,cap,e.aux_voltage,model.bridge_state(),active_limit,
                model.vf.flux_target if not cap else None,
                model.vf.voltage_command if not cap else None)
    v=rate.terminal
    is_,ir,_=k.currents(e.stator_flux,e.rotor_flux)
    machine=ac(v,-(is_+v*k.gc))
    exciter=ac(v,rate.exciter)
    ic=k.cac*rate.voltage if cap else 0j
    capacitor=ac(v,ic)
    ib=2*rate.rectifier*v/(3*abs(v)**2) if abs(v)>1e-12 else 0j
    bridge=ac(v,ib,True)
    boost_i,_,_,_=boost_current(p,e.aux_voltage,e.boost_current_state,e.battery_energy,
        model.max_electrical_step,model.controls.master_on and not model.controls.emergency_stop
        and e.aux_voltage<p.auxiliary_max_voltage)
    boost_output=e.aux_voltage*boost_i
    aux=paths(p,e.battery_energy,boost_output,e.dc_voltage,model.max_electrical_step,model.charger_enabled)
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
        'rectifier':component(rate.rectifier,rate.dc_input+rate.precharge_loss,rate.bridge_loss),
        'precharge_resistor':(component(rate.dc_input+rate.precharge_loss,rate.dc_input,rate.precharge_loss)
                              if model.bridge_state()=='precharge' else component()),
        'dc_link':component(rate.dc_input,dc_heat+aux['charger_input'],storage=rate.dc_input-dc_heat-aux['charger_input'],energy=e.dc_energy),
        'chopper':component(dc_heat,dc_heat),
        'resistor':component(dc_heat,heat=dc_heat),
        'exciter':component(rate.supply,exciter['power'],rate.converter_loss),
        'aux_link':component(boost_output,rate.supply,storage=boost_output-rate.supply,energy=e.aux_energy),
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
        'boost_aux':dc(e.aux_voltage,boost_output),
        'aux_exciter':dc(e.aux_voltage,rate.supply),
        'boost_exciter':dc(e.aux_voltage,rate.supply),
        'battery_terminal':dc(aux['voltage'],aux['power']),
    }
    mismatch=rate.exciter-is_-v*k.gc-ib-ic
    return dict(components=components,connections=ports,kcl=mismatch,
                reactive_residual=machine['reactive']+exciter['reactive']-bridge['reactive']-capacitor['reactive'])
