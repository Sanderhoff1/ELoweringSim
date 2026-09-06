"""Reviewed topology: external small exciter -> stator -> passive bridge -> DC brake.

Full stationary alpha-beta flux dynamics are retained. DC storage is ENERGY;
negative trial energy rejects/subdivides a step, never clips away energy.
Core loss uses the conventional approximate terminal-referred shunt resistance.
"""
from dataclasses import dataclass
import cmath
import math
from typing import NamedTuple

from .mechanical import MechanicalModel, PHYSICS_DT
from .capacitor_rectifier import transfer, midpoint_voltage
from .external_exciter import current as exciter_current
from .examples import small_hoist


@dataclass
class ElectricalState:
    stator_flux: complex=0j
    rotor_flux: complex=0j
    voltage: complex=0j
    dc_energy: float=0.0
    capacitance: float=0.00047
    phase: float=0.0
    time: float=0.0
    chopper_duty: float=0.0
    source_energy: float=0.0
    copper_energy: float=0.0
    core_energy: float=0.0
    dc_brake_energy: float=0.0
    rectifier_energy: float=0.0
    dc_input_energy: float=0.0
    rectifier_loss_energy: float=0.0
    inverter_loss_energy: float=0.0

    @property
    def dc_voltage(self):
        if self.dc_energy<0:
            raise ValueError('Negative DC capacitor energy')
        return math.sqrt(2*self.dc_energy/self.capacitance)


class Rate(NamedTuple):
    ps: complex
    pr: complex
    voltage: complex
    torque: float
    winding_current: complex
    flux: complex
    supply: float
    converter_loss: float
    copper: float
    core: float
    rectifier: float
    dc_input: float
    bridge_loss: float
    exciter: complex
    limited: bool


class Kernel:
    """Constants and torque/derivative paths; no telemetry dictionaries here."""
    def __init__(self,p):
        self.p=p
        self.ls=1/p.stator_leakage
        self.lr=1/p.rotor_leakage
        self.linear=self.ls+self.lr+1/p.magnetizing_inductance
        self.cubic=1/(p.magnetizing_inductance*p.saturation_flux**2)
        self.cac=3*p.capacitor_capacitance*1e-6
        self.cdc=p.dc_capacitance*1e-6
        self.gc=1/p.core_loss_resistance
        self.flux=p.exciter_flux_target
        self.imag=self.flux/p.magnetizing_inductance*(1+(self.flux/p.saturation_flux)**2)

    def currents(self,ps,pr):
        a=ps*self.ls+pr*self.lr
        amplitude=abs(a)
        radius=amplitude/self.linear
        for _ in range(12):
            delta=(self.linear*radius+self.cubic*radius**3-amplitude)/(self.linear+3*self.cubic*radius**2)
            radius-=delta
            if abs(delta)<1e-13: break
        pm=a*(radius/amplitude) if amplitude else 0j
        return (ps-pm)*self.ls,(pr-pm)*self.lr,pm

    def torque(self,ps,pr):
        is_,_,_=self.currents(ps,pr)
        return 1.5*self.p.pole_pairs*(ps.conjugate()*is_).imag

    def winding_rates(self,ps,pr,voltage,omega):
        """Prescribed-terminal machine path, also used for independent validation."""
        is_,ir,_=self.currents(ps,pr)
        return voltage-self.p.stator_resistance*is_, -self.p.rotor_resistance*ir+1j*self.p.pole_pairs*omega*pr

    def stored(self,ps,pr,voltage):
        p=self.p
        is_,ir,pm=self.currents(ps,pr)
        magnetic=.75*(p.stator_leakage*abs(is_)**2+p.rotor_leakage*abs(ir)**2)
        magnetic+=1.5*(abs(pm)**2/(2*p.magnetizing_inductance)+abs(pm)**4/(4*p.magnetizing_inductance*p.saturation_flux**2))
        return magnetic,.75*self.cac*abs(voltage)**2

    def rate(self,y,phase,frequency,omega,vdc,enabled,connected=True):
        p=self.p
        ps,pr,v=y
        is_,ir,pm=self.currents(ps,pr)
        if not connected:
            raise ValueError('Reviewed topology requires the stator connected')
        core_current=v*self.gc if connected else 0j
        machine_power=1.5*(v*(is_+core_current).conjugate()).real
        idc,pac,bridge_loss=transfer(math.sqrt(1.5)*abs(v),vdc,p.rectifier_resistance)
        bridge_current=(2*pac/(3*abs(v)**2))*v if abs(v)>1e-12 else 0j
        axis=cmath.exp(1j*phase)
        we=2*math.pi*frequency
        # Flux-reference feedforward plus field-error feedback. Active demand is
        # independently limited; generated real power cannot use this as a VFD.
        commanded=(1j*we*self.flux+p.stator_resistance*self.imag)*axis
        commanded+=(self.flux*axis-pm)/p.excitation_response
        dv_wanted=1j*we*v+(commanded-v)/p.excitation_response
        requested=is_+core_current+bridge_current+self.cac*dv_wanted
        ie,external,loss,limited=exciter_current(p,v,requested,1j*axis,-machine_power,enabled)
        dv=(ie-is_-core_current-bridge_current)/self.cac
        torque=1.5*p.pole_pairs*(ps.conjugate()*is_).imag
        copper=1.5*(p.stator_resistance*abs(is_)**2+p.rotor_resistance*abs(ir)**2)
        return Rate(v-p.stator_resistance*is_ if connected else 0j,
                    -p.rotor_resistance*ir+1j*p.pole_pairs*omega*pr if connected else 0j,
                    dv,torque,is_,pm,external,loss,copper,1.5*abs(v)**2*self.gc if connected else 0,
                    pac,vdc*idc,bridge_loss,ie,limited)


class ExternalLoweringModel(MechanicalModel):
    external_exciter=True
    dc_exciter=False
    boost_enabled=False
    rectifier_enabled=True
    chopper_active=True
    chopper_enabled=True

    def __init__(self,parameters=None):
        super().__init__(parameters or reviewed_parameters())
        self.motor_connected=self.capacitors_enabled=self.ideal_excitation=True
        self.startup_enabled=True
        self.max_electrical_step=0.0001
        self.kernel=Kernel(self.parameters)
        self.reset()

    def reset(self):
        if self.startup_enabled: self.brake_released=False
        super().reset()
        p=self.parameters
        self.kernel=Kernel(p)
        self.state.omega=p.initial_shaft_rpm*2*math.pi/60
        self.electrical=ElectricalState(complex(p.initial_flux),complex(p.initial_flux),
            complex(math.sqrt(2/3)*p.precharge_voltage),.5*self.kernel.cdc*p.dc_initial_voltage**2,self.kernel.cdc)
        self.qualified_time=0.0
        self.release_time=None
        self.startup_status='MAGNETIZING' if self.startup_enabled else 'MANUAL'
        self.gear_energy=self.drivetrain_energy=self.brake_energy=self.friction_energy=0.0
        self.initial_energy=self.total_energy()
        self.rejected_steps=0

    @property
    def mechanical_dissipation(self):
        return self.gear_energy+self.drivetrain_energy+self.brake_energy+self.friction_energy+self.state.impact_energy

    def total_energy(self):
        p,s,e=self.parameters,self.state,self.electrical
        magnetic,ac=self.kernel.stored(e.stator_flux,e.rotor_flux,e.voltage)
        return magnetic+ac+e.dc_energy+.5*(p.inertia+p.mass*self.effective_radius()**2)*s.omega**2-p.mass*p.gravity*s.position

    def frequency(self):
        p=self.parameters
        if not self.startup_enabled: return p.supply_frequency
        if self.release_time is None: return p.startup_frequency
        fraction=min(1.0,(self.state.time-self.release_time)/p.startup_ramp)
        return p.startup_frequency+(p.supply_frequency-p.startup_frequency)*fraction

    def step(self,dt=PHYSICS_DT):
        if not math.isfinite(dt) or dt<=0: raise ValueError('dt must be positive and finite')
        p=self.parameters
        if self.kernel.p is not p:
            self.kernel=Kernel(p)
        if not self.capacitors_enabled or self.kernel.cac<=0:
            raise ValueError('Reviewed dynamic topology requires nonzero AC capacitance')
        if not self.motor_connected or not self.rectifier_enabled:
            raise ValueError('Reviewed topology requires the machine and passive rectifier connected')
        if self.startup_enabled and self.release_time is None:
            flux=abs(self.kernel.currents(self.electrical.stator_flux,self.electrical.rotor_flux)[2])
            self.qualified_time=self.qualified_time+dt if self.inverter_enabled and flux>=p.startup_flux_fraction*p.exciter_flux_target else 0.0
            self.brake_released=False
            self.startup_status='MAGNETIZING' if self.inverter_enabled else 'WAITING FOR EXTERNAL SUPPLY'
            if self.qualified_time>=p.startup_dwell:
                self.brake_released=True
                self.release_time=self.state.time
                self.startup_status='RELEASING / ACCELERATING'
        elif self.startup_enabled:
            self.startup_status='GENERATING' if self.kernel.torque(self.electrical.stator_flux,self.electrical.rotor_flux)<0 else 'ACCELERATING'
        rate=max(2*math.pi*self.frequency(),p.pole_pairs*abs(self.state.omega),
                 p.stator_resistance/p.stator_leakage,p.rotor_resistance/p.rotor_leakage,
                 1/p.excitation_response,1/(self.kernel.cac*p.core_loss_resistance),
                 1/math.sqrt(self.kernel.cac*min(p.stator_leakage,p.rotor_leakage)),
                 2/(self.kernel.cac*p.rectifier_resistance),1/p.chopper_response)
        hmax=min(self.max_electrical_step,.5/rate,self.kernel.cdc*p.dc_brake_resistance)
        count=max(1,math.ceil(dt/hmax))
        if count>20000: raise ValueError('Parameters require too many substeps')
        for _ in range(count): self._substep(dt/count)

    def _substep(self,h):
        p,s,e,k=self.parameters,self.state,self.electrical,self.kernel
        saved=(s.time,s.position,s.angle,s.omega)
        brake0=s.brake_fraction
        target=0.0 if self.brake_released else 1.0
        s.brake_fraction=target if p.brake_response==0 else target+(brake0-target)*math.exp(-h/(2*p.brake_response))
        if not s.grounded: self._motion(h/2,k.torque(e.stator_flux,e.rotor_flux))
        midomega=s.omega
        s.time,s.position,s.angle,s.omega=saved
        frequency=self.frequency()
        command=min(p.chopper_max_duty,max(0.0,(e.dc_voltage-p.chopper_threshold)/p.chopper_band)) if self.chopper_enabled else 0.0
        duty=command+(e.chopper_duty-command)*math.exp(-h/(2*p.chopper_response))
        vdc=midpoint_voltage(e.dc_energy,k.cdc,h,math.sqrt(1.5)*abs(e.voltage),p.rectifier_resistance,duty/p.dc_brake_resistance)
        y=(e.stator_flux,e.rotor_flux,e.voltage)
        phase=e.phase
        w=2*math.pi*frequency
        args=(frequency,midomega,vdc,self.inverter_enabled,self.motor_connected)
        a=k.rate(y,phase,*args)
        b=k.rate(tuple(y[i]+h*a[i]/2 for i in range(3)),phase+w*h/2,*args)
        c=k.rate(tuple(y[i]+h*b[i]/2 for i in range(3)),phase+w*h/2,*args)
        d=k.rate(tuple(y[i]+h*c[i] for i in range(3)),phase+w*h,*args)
        average=lambda index:(a[index]+2*b[index]+2*c[index]+d[index])/6
        dc_heat=duty*vdc*vdc/p.dc_brake_resistance
        next_energy=e.dc_energy+h*(average(11)-dc_heat)
        values=tuple(y[i]+h*average(i) for i in range(3))
        if next_energy<0 or not all(math.isfinite(z.real) and math.isfinite(z.imag) for z in values):
            s.brake_fraction=brake0
            self.rejected_steps+=1
            if h<1e-10: raise ValueError('Electrical step cannot satisfy positive energy / finite states')
            self._substep(h/2)
            self._substep(h/2)
            return
        torque=average(3)
        # Split the electrical work at contact too: integrating rotating-machine
        # power for a full step after the load lands would create a balance jump.
        bound=p.radius*(abs(s.omega)*h+abs(p.mass*p.gravity*p.radius+torque)*h*h/(p.inertia+p.mass*p.radius**2))
        if not s.grounded and s.position+bound>=p.crane_height:
            self._motion(h,torque)
            crossing=s.position>=p.crane_height
            s.time,s.position,s.angle,s.omega=saved
            if crossing and h>1e-10:
                lo,hi=0.0,h
                for _ in range(35):
                    mid=(lo+hi)/2
                    self._motion(mid,torque)
                    if s.position<p.crane_height: lo=mid
                    else: hi=mid
                    s.time,s.position,s.angle,s.omega=saved
                if 1e-10<hi<h-1e-10:
                    s.brake_fraction=brake0
                    self._substep(hi)
                    self._substep(h-hi)
                    return
        e.stator_flux,e.rotor_flux,e.voltage=values
        e.dc_energy=next_energy
        e.phase=(phase+w*h)%(2*math.pi)
        e.time+=h
        e.chopper_duty=command+(e.chopper_duty-command)*math.exp(-h/p.chopper_response)
        e.source_energy+=h*average(6)
        e.inverter_loss_energy+=h*average(7)
        e.copper_energy+=h*average(8)
        e.core_energy+=h*average(9)
        e.rectifier_energy+=h*average(10)
        e.dc_input_energy+=h*average(11)
        e.rectifier_loss_energy+=h*average(12)
        e.dc_brake_energy+=h*dc_heat
        if s.grounded:
            s.time+=h
        else:
            self._motion(h,torque)
            impact=0.0
            if s.position>=p.crane_height:
                lo,hi=0.0,h
                for _ in range(35):
                    mid=(lo+hi)/2
                    s.time,s.position,s.angle,s.omega=saved
                    self._motion(mid,torque)
                    if s.position<p.crane_height: lo=mid
                    else: hi=mid
                s.time,s.position,s.angle,s.omega=saved
                self._motion(hi,torque)
                s.impact_speed=p.radius*s.omega
                impact=.5*(p.inertia+p.mass*p.radius**2)*s.omega**2
                s.impact_energy=impact
                s.impact_time=s.time
                s.omega=0.0
                s.position=p.crane_height
                s.angle=p.crane_height/p.radius
                s.grounded=True
                s.time=saved[0]+h
            distance=s.angle-saved[2]
            gear=self.gear_loss_torque()*abs(distance)
            drive=p.drivetrain_loss_torque*abs(distance)
            brake=self.brake_capacity()*abs(distance)
            lost=(p.mass*p.gravity*p.radius+torque)*distance-.5*(p.inertia+p.mass*p.radius**2)*(s.omega**2-saved[3]**2)
            self.gear_energy+=gear
            self.drivetrain_energy+=drive
            self.brake_energy+=brake
            self.friction_energy+=lost-gear-drive-brake-impact
        s.brake_fraction=target if p.brake_response==0 else target+(brake0-target)*math.exp(-h/p.brake_response)

    def electrical_readings(self,omega=None):
        if self.kernel.p is not self.parameters:
            self.kernel=Kernel(self.parameters)
        p,s,e,k=self.parameters,self.state,self.electrical,self.kernel
        omega=s.omega if omega is None else omega
        r=k.rate((e.stator_flux,e.rotor_flux,e.voltage),e.phase,self.frequency(),omega,e.dc_voltage,self.inverter_enabled,self.motor_connected)
        v=e.voltage
        total_current=r.winding_current+(v*k.gc if self.motor_connected else 0j)
        power=1.5*(v*total_current.conjugate())
        supply_ac=1.5*(v*r.exciter.conjugate())
        magnetic,ac=k.stored(e.stator_flux,e.rotor_flux,v)
        busfreq=(v.conjugate()*r.voltage).imag/(abs(v)**2*2*math.pi) if abs(v)>1e-3 else 0
        sync=2*math.pi*busfreq/p.pole_pairs
        valid=abs(sync)>1e-3
        duty=e.chopper_duty
        return dict(external_exciter=True,dc_exciter=False,boost_enabled=False,boost_status='NOT IN THIS TOPOLOGY',
            startup_status=self.startup_status,external_supply_power=r.supply,core_loss=r.core,core_energy=e.core_energy,
            gear_energy=self.gear_energy,drivetrain_energy=self.drivetrain_energy,brake_energy=self.brake_energy,friction_energy=self.friction_energy,
            line_voltage=math.sqrt(1.5)*abs(v),bus_frequency=busfreq,
            slip=(sync-omega)/sync if valid else 0,slip_valid=valid,synchronous_rpm=sync*60/(2*math.pi),
            motor_torque=r.torque,motor_mode='GENERATING' if power.real<-.01 else 'MOTORING' if power.real>.01 else 'UNEXCITED / TRANSIENT',
            motor_shaft_power=r.torque*omega,electrical_input=power.real,electrical_export=-power.real,
            stator_loss=1.5*p.stator_resistance*abs(r.winding_current)**2,rotor_loss=r.copper-1.5*p.stator_resistance*abs(r.winding_current)**2,
            machine_line_current=abs(total_current)/math.sqrt(2),machine_reactive_demand=power.imag,
            inverter_current=abs(r.exciter)/math.sqrt(2),inverter_real_power=supply_ac.real,inverter_reactive_supply=supply_ac.imag,
            inverter_status='SUPPLY OFF' if not self.inverter_enabled else 'SMALL EXCITER LIMIT' if r.limited else 'FLUX CONTROL',
            inverter_loss=r.converter_loss,inverter_loss_energy=e.inverter_loss_energy,inverter_dc_power=0,
            capacitor_reactive_supply=-1.5*(v*(k.cac*r.voltage).conjugate()).imag,
            capacitor_line_current=abs(k.cac*r.voltage)/math.sqrt(2),capacitor_energy=ac,magnetic_energy=magnetic,flux_magnitude=abs(r.flux),
            rectifier_enabled=True,rectifier_current=transfer(math.sqrt(1.5)*abs(v),e.dc_voltage,p.rectifier_resistance)[0],
            rectifier_power=r.rectifier,rectifier_energy=e.rectifier_energy,dc_input_power=r.dc_input,
            dc_input_energy=e.dc_input_energy,rectifier_loss=r.bridge_loss,rectifier_loss_energy=e.rectifier_loss_energy,
            dc_voltage=e.dc_voltage,dc_energy=e.dc_energy,dc_brake_power=duty*e.dc_voltage**2/p.dc_brake_resistance,
            dc_brake_energy=e.dc_brake_energy,chopper_active=True,chopper_enabled=self.chopper_enabled,
            chopper_duty=duty,chopper_command=min(p.chopper_max_duty,max(0,(e.dc_voltage-p.chopper_threshold)/p.chopper_band)) if self.chopper_enabled else 0,
            load_power=0,load_energy=0,source_energy=e.source_energy,copper_energy=e.copper_energy,
            beyond_peak=False,effective_peak_torque=0,compensation_fraction=0,matching_capacitance=0)

    def readings(self):
        r=super().readings()
        e=self.electrical
        r['energy_residual']=self.total_energy()-self.initial_energy+e.copper_energy+e.core_energy+e.inverter_loss_energy+e.rectifier_loss_energy+e.dc_brake_energy+self.mechanical_dissipation-e.source_energy
        return r


def reviewed_parameters(**overrides):
    values=dict(initial_flux=0,gearbox_efficiency=.9,drivetrain_loss_torque=.1,
                chopper_threshold=500,dc_brake_resistance=330)
    values.update(overrides)
    return small_hoist(**values)
