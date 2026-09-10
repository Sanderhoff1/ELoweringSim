"""Stationary alpha-beta induction machine and delta capacitor voltage states.

Complex vectors use amplitude-invariant Clarke coordinates (phase peak units).
This is a circuit/flux model, not a switching model or imposed growth envelope.
"""
from dataclasses import dataclass
import cmath
import math
from .rectifier import bridge, K
from .converter_controls import chopper as chopper_control, chopper_target, exciter
from .boost import support

ELECTRICAL_DT = 0.0001


@dataclass
class ElectricalState:
    stator_flux: complex = 0j
    rotor_flux: complex = 0j
    voltage: complex = 0j
    time: float = 0.0
    source_energy: float = 0.0
    load_energy: float = 0.0
    copper_energy: float = 0.0
    dc_voltage: float = 0.0
    dc_brake_energy: float = 0.0
    rectifier_loss_energy: float = 0.0
    chopper_duty: float = 0.0
    inverter_loss_energy: float = 0.0
    inverter_ac_energy: float = 0.0
    boost_current: float = 0.0
    battery_energy: float = 0.0
    boost_loss_energy: float = 0.0


def initial_state(p):
    return ElectricalState(complex(p.initial_flux), complex(p.initial_flux),
                           complex(math.sqrt(2/3)*p.precharge_voltage),
                           dc_voltage=p.dc_initial_voltage)


def currents(p, stator_flux, rotor_flux, connected=True):
    """Invert the nonlinear flux/current relation with a scalar monotone solve."""
    if connected:
        a = stator_flux/p.stator_leakage + rotor_flux/p.rotor_leakage
        b = 1/p.stator_leakage + 1/p.rotor_leakage
    else:  # open stator: is=0, rotor still has decaying stored field
        a, b = rotor_flux/p.rotor_leakage, 1/p.rotor_leakage
    linear = b+1/p.magnetizing_inductance
    cubic = 1/(p.magnetizing_inductance*p.saturation_flux**2)
    magnitude = abs(a)
    radius = min(magnitude/linear, (magnitude/cubic)**(1/3)) if magnitude else 0.0
    for _ in range(12):
        correction = (linear*radius+cubic*radius**3-magnitude)/(linear+3*cubic*radius**2)
        radius -= correction
        if abs(correction) < 1e-13*max(1.0, radius):
            break
    flux = a*(radius/magnitude) if magnitude else 0j
    stator_current = (stator_flux-flux)/p.stator_leakage if connected else 0j
    rotor_current = (rotor_flux-flux)/p.rotor_leakage
    return stator_current, rotor_current, flux


def circuit(p, y, time, omega, inverter, capacitors, connected=True, rectifier=False,
            chopper=False, dc_exciter=False, chopper_enabled=True, boost_enabled=False):
    ps, pr, vc = y[:3]
    dc_voltage = y[3] if len(y)>3 else 0.0
    duty = float(y[4].real) if len(y)>4 else 0.0
    boost_current=y[5] if len(y)>5 else 0.0
    auxiliary=support(p,dc_voltage,boost_current,boost_enabled and rectifier)
    # Commanded excitation uses its command. Passive capacitor operation has no
    # fake command; rotor electrical frequency is this legacy model's estimator.
    control_frequency=(p.supply_frequency if inverter else
                       abs(p.pole_pairs*omega)/(2*math.pi))
    command, dduty = (chopper_control(p,float(dc_voltage.real),duty,
                                     chopper_enabled,control_frequency)
                      if chopper else (1.0,0.0))
    is_, ir, pm = currents(p, ps, pr, connected)
    ceq = 3*p.capacitor_capacitance*1e-6 if capacitors else 0.0
    if rectifier and not inverter and not ceq:
        raise ValueError('Passive rectifier needs a connected, nonzero AC capacitor bank in this averaged model.')
    if dc_exciter and (not rectifier or not ceq):
        raise ValueError('DC-fed excitation requires the DC path and nonzero connected AC capacitors.')
    inv = dict(loss=0.0,dc_power=0.0,dc_current=0.0,status='IDEAL' if inverter else 'OFF',
               current_limited=False,voltage_limited=False,maximum_voltage=0.0)
    frequency = 2*math.pi*p.supply_frequency
    reference = math.sqrt(2/3)*p.volts_per_hz*p.supply_frequency*cmath.exp(1j*frequency*time)
    # The Phase 5 path replaces the earlier balanced AC test resistor.
    conductance = 0.0 if rectifier else 1/p.ac_load_resistance
    if ceq:
        voltage = vc
        dc = bridge(p, voltage, dc_voltage, rectifier, duty if chopper else 1.0)
        drawn_current = voltage*conductance+dc['ac_current']
        if dc_exciter:
            wanted_dv=1j*frequency*voltage+(reference-voltage)/p.excitation_response
            requested=is_+drawn_current+ceq*wanted_dv
            inv=exciter(p,voltage,requested,float(dc_voltage.real),inverter)
            source_current=inv['current']
            dv=(source_current-is_-drawn_current)/ceq
            dc['derivative']-=inv['dc_current']/(p.dc_capacitance*1e-6)
        elif inverter:
            dv = 1j*frequency*voltage+(reference-voltage)/p.excitation_response
            source_current = is_+drawn_current+ceq*dv
        else:
            source_current = 0j
            dv = -(is_+drawn_current)/ceq
    else:
        # No capacitor state participates: algebraic bus boundary.
        if inverter:
            voltage = reference
        else:
            voltage = -p.ac_load_resistance*is_ if not rectifier else 0j
        dc = bridge(p, voltage, dc_voltage, rectifier, duty if chopper else 1.0)
        source_current = is_+voltage*conductance+dc['ac_current'] if inverter else 0j
        dv = 0j
    torque = 1.5*p.pole_pairs*(ps.conjugate()*is_).imag if connected else 0.0
    if rectifier:
        dc['derivative']+=auxiliary['current']/(p.dc_capacitance*1e-6)
    dps = voltage-p.stator_resistance*is_ if connected else 0j
    dpr = -p.rotor_resistance*ir+1j*p.pole_pairs*omega*pr
    source_power = 1.5*(voltage*source_current.conjugate()).real
    load_power = 1.5*abs(voltage)**2*conductance
    copper = 1.5*(p.stator_resistance*abs(is_)**2+p.rotor_resistance*abs(ir)**2)
    derivatives = (dps, dpr, dv, dc['derivative']) if len(y)>3 else (dps, dpr, dv)
    if len(y)>4:
        derivatives += (dduty,)
    if len(y)>5:
        derivatives += (auxiliary['derivative'],)
    return derivatives, dict(voltage=voltage, source_current=source_current,
        stator_current=is_, rotor_current=ir, magnetizing_flux=pm, torque=torque,
        source_power=source_power, load_power=load_power, copper_power=copper,
        rotor_loss=1.5*p.rotor_resistance*abs(ir)**2, ceq=ceq, dc=dc, inv=inv,
        external_power=0.0 if dc_exciter else source_power, duty_command=command,
        chopper_target_voltage=chopper_target(p,control_frequency),
        chopper_target_frequency=control_frequency,boost=auxiliary)


def stored_energy(p, y, capacitors=True, connected=True):
    is_, ir, pm = currents(p, y[0], y[1], connected)
    magnetic = 0.75*(p.stator_leakage*abs(is_)**2+p.rotor_leakage*abs(ir)**2)
    magnetic += 1.5*(abs(pm)**2/(2*p.magnetizing_inductance)
                    +abs(pm)**4/(4*p.magnetizing_inductance*p.saturation_flux**2))
    ceq = 3*p.capacitor_capacitance*1e-6 if capacitors else 0.0
    return magnetic, 0.75*ceq*abs(y[2])**2


def advance(p, state, dt, omega, inverter, capacitors, connected=True, rectifier=False,
            chopper=False, dc_exciter=False, chopper_enabled=True, boost_enabled=False):
    """RK4 step with an externally held shaft speed; returns mean torque."""
    y = (state.stator_flux, state.rotor_flux, state.voltage, state.dc_voltage, state.chopper_duty,state.boost_current)
    if rectifier and state.dc_voltage<0:
        raise ValueError('DC voltage cannot start negative')
    switches=(inverter,capacitors,connected,rectifier,chopper,dc_exciter,chopper_enabled,boost_enabled)
    def subdivide():
        if dt<1e-12:
            raise ValueError('Legacy voltage integration cannot resolve DC depletion')
        first=advance(p,state,dt/2,omega,*switches)
        second=advance(p,state,dt/2,omega,*switches)
        return (first+second)/2
    k1, r1 = circuit(p, y, state.time, omega, *switches)
    stage=tuple(v+dt*k/2 for v,k in zip(y,k1))
    if rectifier and stage[3].real<0: return subdivide()
    k2, r2 = circuit(p, stage, state.time+dt/2, omega, *switches)
    stage=tuple(v+dt*k/2 for v,k in zip(y,k2))
    if rectifier and stage[3].real<0: return subdivide()
    k3, r3 = circuit(p, stage, state.time+dt/2, omega, *switches)
    stage=tuple(v+dt*k for v,k in zip(y,k3))
    if rectifier and stage[3].real<0: return subdivide()
    k4, r4 = circuit(p, stage, state.time+dt, omega, *switches)
    values = tuple(v+dt*(a+2*b+2*c+d)/6 for v,a,b,c,d in zip(y,k1,k2,k3,k4))
    if rectifier and values[3].real<0: return subdivide()
    if not all(math.isfinite(v.real) and math.isfinite(v.imag) for v in values):
        raise ValueError("Dynamic electrical integration diverged; reduce parameter extremes or timestep.")
    state.stator_flux, state.rotor_flux, state.voltage = values[:3]
    state.dc_voltage = float(values[3].real)
    state.chopper_duty = float(values[4].real)
    state.boost_current=float(values[5].real)
    def mean(key):
        return (r1[key]+2*r2[key]+2*r3[key]+r4[key])/6
    state.source_energy += dt*mean('external_power')
    for attribute,key in (('battery_energy','battery_power'),('boost_loss_energy','loss')):
        setattr(state,attribute,getattr(state,attribute)+dt*(r1['boost'][key]+2*r2['boost'][key]+2*r3['boost'][key]+r4['boost'][key])/6)
    state.inverter_ac_energy += dt*mean('source_power')
    state.inverter_loss_energy += dt*(r1['inv']['loss']+2*r2['inv']['loss']+2*r3['inv']['loss']+r4['inv']['loss'])/6
    state.load_energy += dt*mean('load_power')
    state.copper_energy += dt*mean('copper_power')
    state.dc_brake_energy += dt*(r1['dc']['brake_power']+2*r2['dc']['brake_power']+2*r3['dc']['brake_power']+r4['dc']['brake_power'])/6
    state.rectifier_loss_energy += dt*(r1['dc']['loss']+2*r2['dc']['loss']+2*r3['dc']['loss']+r4['dc']['loss'])/6
    state.time += dt
    return mean('torque')


def readings(p, state, omega, inverter, capacitors, connected=True, rectifier=False,
             chopper=False, dc_exciter=False, chopper_enabled=True,boost_enabled=False):
    y = (state.stator_flux, state.rotor_flux, state.voltage, state.dc_voltage,state.chopper_duty,state.boost_current)
    derivatives, r = circuit(p, y, state.time, omega, inverter, capacitors, connected, rectifier,chopper,dc_exciter,chopper_enabled,boost_enabled)
    voltage, is_ = r['voltage'], r['stator_current']
    magnitude = abs(voltage)
    # Instantaneous vector angular velocity, undefined near a dead bus.
    bus_frequency = (voltage.conjugate()*derivatives[2]).imag/(magnitude**2*2*math.pi) if magnitude>1e-3 and r['ceq'] else (p.supply_frequency if inverter else 0.0)
    sync = 2*math.pi*bus_frequency/p.pole_pairs
    slip_valid = abs(sync)>1e-3 and magnitude>1e-3
    terminal_power = 1.5*(voltage*is_.conjugate()).real
    q_machine = 1.5*(voltage*is_.conjugate()).imag
    q_inv = 1.5*(voltage*r['source_current'].conjugate()).imag
    cap_current = r['ceq']*derivatives[2]
    q_cap = -1.5*(voltage*cap_current.conjugate()).imag
    magnetic, capacitor = stored_energy(p, y, capacitors, connected)
    mode = 'DISCONNECTED' if not connected else ('GENERATING' if terminal_power < -0.01 else 'MOTORING' if terminal_power>0.01 else 'UNEXCITED / TRANSIENT')
    return dict(boost_enabled=boost_enabled and rectifier,boost_status=r['boost']['status'],
        boost_power=r['boost']['output_power'],battery_power=r['boost']['battery_power'],
        battery_current=r['boost']['battery_current'],boost_loss=r['boost']['loss'],
        battery_energy=state.battery_energy,boost_loss_energy=state.boost_loss_energy,
        chopper_active=chopper, chopper_enabled=chopper_enabled,
        chopper_duty=state.chopper_duty if chopper else 1.0, chopper_command=r['duty_command'],
        chopper_target_voltage=r['chopper_target_voltage'],
        chopper_target_frequency=r['chopper_target_frequency'],
        chopper_current=(state.chopper_duty*state.dc_voltage/p.dc_brake_resistance
                         if chopper and rectifier else 0.0),
        main_dc_overvoltage_limit=p.main_dc_max_voltage,
        main_dc_overvoltage=state.dc_voltage>p.main_dc_max_voltage,
        dc_exciter=dc_exciter,inverter_status=r['inv']['status'],
        inverter_loss=r['inv']['loss'],inverter_loss_energy=state.inverter_loss_energy,
        inverter_dc_power=r['inv']['dc_power'],inverter_voltage_limit=r['inv']['maximum_voltage']*math.sqrt(3/2),
        inverter_current_limited=r['inv']['current_limited'],inverter_voltage_limited=r['inv']['voltage_limited'],
        rectifier_enabled=rectifier, dc_voltage=state.dc_voltage if rectifier else 0.0,
        dc_energy=0.5*p.dc_capacitance*1e-6*state.dc_voltage**2 if rectifier else 0.0,
        rectifier_power=r['dc']['power'], dc_input_power=r['dc']['dc_power'],
        rectifier_loss=r['dc']['loss'], dc_brake_power=r['dc']['brake_power'],
        rectifier_current=r['dc']['current'], dc_brake_energy=state.dc_brake_energy,
        rectifier_loss_energy=state.rectifier_loss_energy,
        line_voltage=math.sqrt(3/2)*magnitude, bus_frequency=bus_frequency,
        slip=(sync-omega)/sync if slip_valid else 0.0, slip_valid=slip_valid,
        synchronous_rpm=sync*60/(2*math.pi), motor_torque=r['torque'],
        motor_mode=mode, motor_shaft_power=r['torque']*omega,
        electrical_input=terminal_power, electrical_export=-terminal_power,
        rotor_loss=r['rotor_loss'], stator_loss=r['copper_power']-r['rotor_loss'],
        machine_line_current=abs(is_)/math.sqrt(2),
        inverter_current=abs(r['source_current'])/math.sqrt(2),
        inverter_real_power=r['source_power'], inverter_reactive_supply=q_inv,
        capacitor_reactive_supply=q_cap, capacitor_line_current=abs(cap_current)/math.sqrt(2),
        machine_reactive_demand=q_machine, magnetic_energy=magnetic,
        capacitor_energy=capacitor, flux_magnitude=abs(r['magnetizing_flux']),
        load_power=r['load_power'], source_energy=state.source_energy,
        load_energy=state.load_energy, copper_energy=state.copper_energy,
        beyond_peak=False, effective_peak_torque=0.0,
        compensation_fraction=q_cap/q_machine if abs(q_machine)>1e-6 else 0,
        matching_capacitance=0.0)
