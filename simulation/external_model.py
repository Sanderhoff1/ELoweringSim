"""Finite battery/boost topology: small exciter -> stator -> passive bridge -> DC brake.

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
from .auxiliary import boost_limit, paths


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
    battery_energy: float=0.0
    battery_loss_energy: float=0.0
    boost_loss_energy: float=0.0
    charger_loss_energy: float=0.0
    charger_energy: float=0.0
    precharge_loss_energy: float=0.0

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
    terminal: complex


class Kernel:
    """Constants and torque/derivative paths; no telemetry dictionaries here."""
    def __init__(self,p):
        self.p=p
        self.supply_limit=boost_limit(p)
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

    def rate(self,y,phase,frequency,omega,vdc,enabled,connected=True, capacitor_mode=True):
        p=self.p
        ps,pr,v=y
        is_,ir,pm=self.currents(ps,pr)
        if not connected:
            raise ValueError('Reviewed topology requires the stator connected')
        axis=cmath.exp(1j*phase)
        we=2*math.pi*frequency
        commanded=1j*we*ps+p.stator_resistance*is_
        field_axis=pm/abs(pm) if abs(pm)>1e-9 else axis
        commanded+=(self.flux*field_axis-pm)/p.excitation_response
        source=commanded+p.inverter_output_resistance*is_
        ceiling=p.boost_target_voltage/math.sqrt(3)
        source*=min(1.,ceiling/max(abs(source),1e-12))
        def network(v):
            idc,pac,bridge_loss=transfer(math.sqrt(1.5)*abs(v),vdc,p.rectifier_resistance)
            ib=(2*pac/(3*abs(v)**2))*v if abs(v)>1e-12 else 0j
            load=is_+v*self.gc+ib
            wanted=1j*we*v+(commanded-v)/p.excitation_response
            request=load+self.cac*wanted if capacitor_mode else (source-v)/p.inverter_output_resistance
            ie,external,loss,limited=exciter_current(p,v,request,1j*axis,
                -1.5*(v*(is_+v*self.gc).conjugate()).real,enabled,self.supply_limit)
            return load-ie,ie,external,loss,limited,idc,pac,bridge_loss
        if not capacitor_mode:
            solved=False
            for seed in (v,commanded,0j,-is_/self.gc):
                v=seed
                for iteration in range(60):
                    f=network(v)[0]
                    if abs(f)<1e-9:
                        solved=True
                        break
                    eps=1e-5
                    dx=(network(v+eps)[0]-network(v-eps)[0])/(2*eps)
                    dy=(network(v+1j*eps)[0]-network(v-1j*eps)[0])/(2*eps)
                    det=dx.real*dy.imag-dy.real*dx.imag
                    if abs(det)<1e-16: break
                    step=complex((f.real*dy.imag-f.imag*dy.real)/det,
                                 (dx.real*f.imag-dx.imag*f.real)/det)
                    scale=1.
                    for _ in range(24):
                        trial=v-scale*step
                        if abs(network(trial)[0])<abs(f): break
                        scale*=.5
                    else: break
                    v=trial
                if solved: break
            if not solved:
                # No stable feasible converter point: block the exciter and
                # solve the passive network. Inductive energy then goes to the
                # bridge/core; it cannot disappear into a voltage clamp.
                lo,hi=0.,abs(is_)/self.gc
                for _ in range(70):
                    radius=(lo+hi)/2
                    _,power,_=transfer(math.sqrt(1.5)*radius,vdc,p.rectifier_resistance)
                    current=self.gc*radius+(2*power/(3*radius) if radius else 0.)
                    if current>abs(is_): hi=radius
                    else: lo=radius
                v=-is_*radius/abs(is_) if abs(is_) else 0j
                enabled=False
        mismatch,ie,external,loss,limited,idc,pac,bridge_loss=network(v)
        if not capacitor_mode and not solved: limited=True
        dv=-mismatch/self.cac if capacitor_mode else 0j
        torque=1.5*p.pole_pairs*(ps.conjugate()*is_).imag
        copper=1.5*(p.stator_resistance*abs(is_)**2+p.rotor_resistance*abs(ir)**2)
        return Rate(v-p.stator_resistance*is_ if connected else 0j,
                    -p.rotor_resistance*ir+1j*p.pole_pairs*omega*pr if connected else 0j,
                    dv,torque,is_,pm,external,loss,copper,1.5*abs(v)**2*self.gc if connected else 0,
                    pac,vdc*idc,bridge_loss,ie,limited,v)


class ExternalLoweringModel(MechanicalModel):
    external_exciter=True
    dc_exciter=False
    boost_enabled=False
    rectifier_enabled=True
    chopper_active=True
    chopper_enabled=True

    def __init__(self,parameters=None):
        super().__init__(parameters or reviewed_parameters())
        self.motor_connected=self.ideal_excitation=True
        self.excitation_mode='exciter'       # 'exciter' or 'capacitor'
        self.start_mode='residual'           # residual, external_supply, precharged
        self.capacitors_enabled=False
        self.startup_enabled=True
        self.charger_enabled=True
        self.max_electrical_step=0.0001
        self.kernel=Kernel(self.parameters)
        self.reset()

    def reset(self):
        if self.startup_enabled: self.brake_released=False
        super().reset()
        p=self.parameters
        self.kernel=Kernel(p)
        self.state.omega=p.initial_shaft_rpm*2*math.pi/60
        cap_mode=self.excitation_mode == 'capacitor'
        self.capacitors_enabled=cap_mode
        flux = p.initial_flux if self.start_mode == 'residual' else 0.0
        # Precharge is an initial stored-energy transfer from the finite battery,
        # never an artificial AC source.  The capacitor starts charged only in
        # the explicit capacitor-precharge startup mode.
        precharge = min(p.precharge_voltage,p.boost_target_voltage/math.sqrt(2)) if cap_mode and self.start_mode == 'precharged' else 0.0
        battery0=p.battery_capacity_wh*3600*p.battery_initial_soc/100
        cap_energy=.75*self.kernel.cac*(math.sqrt(2/3)*precharge)**2 if cap_mode else 0.0
        cap_energy=min(cap_energy,battery0*p.precharge_efficiency)
        precharge=math.sqrt(2*cap_energy/self.kernel.cac) if cap_mode and self.kernel.cac else 0.0
        drawn=cap_energy/max(p.precharge_efficiency,1e-12)
        battery=max(0.0,battery0-drawn)
        self.electrical=ElectricalState(complex(flux),complex(flux),complex(math.sqrt(2/3)*precharge),
            .5*self.kernel.cdc*p.dc_initial_voltage**2,self.kernel.cdc,battery_energy=battery,
            precharge_loss_energy=max(0.0,drawn-cap_energy))
        self.support_complete=False
        self.support_qualified_time=0.0
        self.qualified_time=0.0
        self.release_time=None
        self.startup_status='MAGNETIZING' if self.startup_enabled else 'MANUAL'
        self.gear_energy=self.drivetrain_energy=self.brake_energy=self.friction_energy=0.0
        self.initial_energy=self.total_energy()+self.electrical.precharge_loss_energy
        self.rejected_steps=0

    def startup_support_active(self):
        return (self.excitation_mode=='capacitor' and self.start_mode=='external_supply'
                and not self.support_complete)

    def excitation_active(self):
        return (self.inverter_enabled and self.electrical.battery_energy>0
                and (self.excitation_mode=='exciter' or self.startup_support_active()))

    @property
    def mechanical_dissipation(self):
        return self.gear_energy+self.drivetrain_energy+self.brake_energy+self.friction_energy+self.state.impact_energy

    def total_energy(self):
        p,s,e=self.parameters,self.state,self.electrical
        magnetic,ac=self.kernel.stored(e.stator_flux,e.rotor_flux,e.voltage)
        return magnetic+(ac if self.excitation_mode=='capacitor' else 0.0)+e.dc_energy+e.battery_energy+.5*(p.inertia+p.mass*self.effective_radius()**2)*s.omega**2-p.mass*p.gravity*s.position

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
        if self.excitation_mode not in ('exciter','capacitor'):
            raise ValueError('excitation_mode must be exciter or capacitor')
        if self.excitation_mode == 'capacitor' and self.kernel.cac<=0:
            raise ValueError('Capacitor-only mode requires positive capacitance')
        if not self.motor_connected or not self.rectifier_enabled:
            raise ValueError('Reviewed topology requires the machine and passive rectifier connected')
        if self.startup_support_active():
            field=abs(self.kernel.currents(self.electrical.stator_flux,self.electrical.rotor_flux)[2])
            self.support_qualified_time=(self.support_qualified_time+dt if field>=p.startup_flux_fraction*p.exciter_flux_target else 0.)
            if self.support_qualified_time>=p.startup_dwell:
                self.support_complete=True
        if self.startup_enabled and self.release_time is None:
            flux=abs(self.kernel.currents(self.electrical.stator_flux,self.electrical.rotor_flux)[2])
            field_available=(self.excitation_mode=='exciter' and self.inverter_enabled) or self.excitation_mode=='capacitor'
            self.qualified_time=self.qualified_time+dt if field_available and flux>=p.startup_flux_fraction*p.exciter_flux_target else 0.0
            self.brake_released=False
            self.startup_status='MAGNETIZING' if field_available else 'WAITING FOR BATTERY EXCITATION'
            if self.qualified_time>=p.startup_dwell:
                self.brake_released=True
                self.release_time=self.state.time
                self.startup_status='RELEASING / ACCELERATING'
        elif self.startup_enabled:
            self.startup_status='GENERATING' if self.kernel.torque(self.electrical.stator_flux,self.electrical.rotor_flux)<0 else 'ACCELERATING'
        rate=max(2*math.pi*self.frequency(),p.pole_pairs*abs(self.state.omega),
                 p.stator_resistance/p.stator_leakage,p.rotor_resistance/p.rotor_leakage,
                 1/p.excitation_response,
                 (1/(self.kernel.cac*p.core_loss_resistance) if self.excitation_mode=='capacitor' else 0),
                 (1/math.sqrt(self.kernel.cac*min(p.stator_leakage,p.rotor_leakage)) if self.excitation_mode=='capacitor' else 0),
                 (2/(self.kernel.cac*p.rectifier_resistance) if self.excitation_mode=='capacitor' else 0),1/p.chopper_response)
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
        exciter_on=self.excitation_active()
        k.supply_limit=boost_limit(p,e.battery_energy,h)
        args=(frequency,midomega,vdc,exciter_on,self.motor_connected,self.excitation_mode=='capacitor')
        a=k.rate(y,phase,*args)
        b=k.rate(tuple(y[i]+h*a[i]/2 for i in range(3)),phase+w*h/2,*args)
        c=k.rate(tuple(y[i]+h*b[i]/2 for i in range(3)),phase+w*h/2,*args)
        d=k.rate(tuple(y[i]+h*c[i] for i in range(3)),phase+w*h,*args)
        average=lambda index:(a[index]+2*b[index]+2*c[index]+d[index])/6
        dc_heat=duty*vdc*vdc/p.dc_brake_resistance
        # Main DC link may recharge the auxiliary battery.  This is an
        # isolated averaged charger: it cannot reverse or charge past 100%.
        aux=paths(p,e.battery_energy,average(6),vdc,h,self.charger_enabled)
        charger_in,charger_out=aux['charger_input'],aux['charger_output']
        next_energy=e.dc_energy+h*(average(11)-dc_heat-charger_in)
        values=tuple(y[i]+h*average(i) for i in range(3))
        old_mag,old_cap=k.stored(y[0],y[1],y[2])
        new_mag,new_cap=k.stored(values[0],values[1],values[2])
        ac_change=new_mag-old_mag+(new_cap-old_cap if self.excitation_mode=='capacitor' else 0.)
        ac_work=h*(average(6)-average(7)-average(8)-average(9)-average(10)-average(3)*midomega)
        integration_error=abs(ac_change-ac_work)
        if next_energy<0 or integration_error>1e-8+h*1e-4 or not all(math.isfinite(z.real) and math.isfinite(z.imag) for z in values):
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
        if self.excitation_mode=='exciter':
            e.voltage=k.rate(values,phase+w*h,*args).terminal
        e.dc_energy=next_energy
        e.phase=(phase+w*h)%(2*math.pi)
        e.time+=h
        e.chopper_duty=command+(e.chopper_duty-command)*math.exp(-h/p.chopper_response)
        # Converter input comes solely from the finite 24 V battery.
        e.battery_energy+=h*aux['storage']
        e.battery_loss_energy+=h*aux['heat']
        e.boost_loss_energy+=h*aux['boost_heat']
        e.charger_loss_energy+=h*(charger_in-charger_out)
        e.charger_energy+=h*charger_out
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
        exciter_on=self.excitation_active()
        r=k.rate((e.stator_flux,e.rotor_flux,e.voltage),e.phase,self.frequency(),omega,e.dc_voltage,exciter_on,self.motor_connected,self.excitation_mode=='capacitor')
        v=r.terminal
        total_current=r.winding_current+(v*k.gc if self.motor_connected else 0j)
        power=1.5*(v*total_current.conjugate())
        supply_ac=1.5*(v*r.exciter.conjugate())
        magnetic,ac=k.stored(e.stator_flux,e.rotor_flux,v)
        terminal_rate=r.voltage
        if self.excitation_mode=='exciter' and abs(v)>1e-3:
            eps=1e-7
            df=((p.supply_frequency-p.startup_frequency)/p.startup_ramp
                if self.startup_enabled and self.release_time is not None and 0<=s.time-self.release_time<p.startup_ramp else 0.)
            domega=0. if s.grounded else (self._drive(r.torque)-p.damping*omega)/(p.inertia+p.mass*p.radius**2)
            aux_probe=paths(p,e.battery_energy,r.supply,e.dc_voltage,self.max_electrical_step,self.charger_enabled)
            dvdc=(r.dc_input-e.chopper_duty*e.dc_voltage**2/p.dc_brake_resistance-aux_probe['charger_input'])/(k.cdc*e.dc_voltage) if e.dc_voltage>1e-5 else 0.
            probe=k.rate((e.stator_flux+eps*r.ps,e.rotor_flux+eps*r.pr,v),e.phase+eps*2*math.pi*self.frequency(),
                self.frequency()+eps*df,omega+eps*domega,max(0.,e.dc_voltage+eps*dvdc),exciter_on,True,False)
            terminal_rate=(probe.terminal-v)/eps
        busfreq=(v.conjugate()*terminal_rate).imag/(abs(v)**2*2*math.pi) if abs(v)>1e-3 else 0
        sync=2*math.pi*busfreq/p.pole_pairs
        valid=abs(sync)>1e-3
        duty=e.chopper_duty
        battery_capacity=p.battery_capacity_wh*3600
        aux=paths(p,e.battery_energy,r.supply,e.dc_voltage,self.max_electrical_step,self.charger_enabled)
        battery_power=aux['power']
        return dict(external_exciter=False,dc_exciter=False,boost_enabled=exciter_on,boost_status='SUPPLYING EXCITER' if exciter_on else 'OFF',
            excitation_mode=self.excitation_mode,start_mode=self.start_mode,
            startup_support=self.startup_support_active(),support_complete=self.support_complete,charger_enabled=self.charger_enabled,flux_angle=cmath.phase(r.flux),
            startup_status=self.startup_status,external_supply_power=0.0,core_loss=r.core,core_energy=e.core_energy,
            gear_energy=self.gear_energy,drivetrain_energy=self.drivetrain_energy,brake_energy=self.brake_energy,friction_energy=self.friction_energy,
            line_voltage=math.sqrt(1.5)*abs(v),bus_frequency=busfreq,
            slip=(sync-omega)/sync if valid else 0,slip_valid=valid,synchronous_rpm=sync*60/(2*math.pi),
            motor_torque=r.torque,motor_mode='GENERATING' if power.real<-.01 else 'MOTORING' if power.real>.01 else 'UNEXCITED / TRANSIENT',
            motor_shaft_power=r.torque*omega,electrical_input=power.real,electrical_export=-power.real,
            stator_loss=1.5*p.stator_resistance*abs(r.winding_current)**2,rotor_loss=r.copper-1.5*p.stator_resistance*abs(r.winding_current)**2,
            machine_line_current=abs(total_current)/math.sqrt(2),machine_reactive_demand=power.imag,
            inverter_current=abs(r.exciter)/math.sqrt(2),inverter_real_power=supply_ac.real,inverter_reactive_supply=supply_ac.imag,
            inverter_status='STARTUP SUPPORT' if self.startup_support_active() and exciter_on else 'DISCONNECTED' if self.excitation_mode=='capacitor' else 'BATTERY EMPTY / OFF' if not exciter_on else 'SMALL EXCITER LIMIT' if r.limited else 'FLUX CONTROL',
            inverter_loss=r.converter_loss,inverter_loss_energy=e.inverter_loss_energy,inverter_dc_power=0,
            capacitor_reactive_supply=-1.5*(v*(k.cac*r.voltage).conjugate()).imag if self.excitation_mode=='capacitor' else 0.0,
            capacitor_line_current=abs(k.cac*r.voltage)/math.sqrt(2) if self.excitation_mode=='capacitor' else 0.0,
            capacitor_energy=ac if self.excitation_mode=='capacitor' else 0.0,magnetic_energy=magnetic,flux_magnitude=abs(r.flux),
            rectifier_enabled=True,rectifier_current=transfer(math.sqrt(1.5)*abs(v),e.dc_voltage,p.rectifier_resistance)[0],
            rectifier_power=r.rectifier,rectifier_energy=e.rectifier_energy,dc_input_power=r.dc_input,
            dc_input_energy=e.dc_input_energy,rectifier_loss=r.bridge_loss,rectifier_loss_energy=e.rectifier_loss_energy,
            dc_voltage=e.dc_voltage,dc_energy=e.dc_energy,dc_brake_power=duty*e.dc_voltage**2/p.dc_brake_resistance,
            dc_brake_energy=e.dc_brake_energy,chopper_active=True,chopper_enabled=self.chopper_enabled,
            chopper_duty=duty,chopper_command=min(p.chopper_max_duty,max(0,(e.dc_voltage-p.chopper_threshold)/p.chopper_band)) if self.chopper_enabled else 0,
            battery_voltage=aux['voltage'],battery_current=aux['current'],battery_power=battery_power,
            battery_soc=100*e.battery_energy/battery_capacity,battery_remaining_wh=e.battery_energy/3600,
            battery_energy=e.battery_energy,battery_loss=aux['heat'],battery_loss_energy=e.battery_loss_energy,
            boost_power=r.supply,boost_loss=(r.supply/p.boost_efficiency-r.supply) if exciter_on else 0,boost_loss_energy=e.boost_loss_energy,
            charger_power=-aux['charger_input'],charger_loss=aux['charger_heat'],
            charger_loss_energy=e.charger_loss_energy,charger_energy=e.charger_energy,
            load_power=0,load_energy=0,source_energy=0,copper_energy=e.copper_energy,
            beyond_peak=False,effective_peak_torque=0,compensation_fraction=0,matching_capacitance=0)

    def readings(self):
        r=super().readings()
        e=self.electrical
        r['energy_residual']=self.total_energy()-self.initial_energy+e.copper_energy+e.core_energy+e.inverter_loss_energy+e.rectifier_loss_energy+e.dc_brake_energy+e.boost_loss_energy+e.charger_loss_energy+e.precharge_loss_energy+e.battery_loss_energy+self.mechanical_dissipation
        from .power_diagnostics import diagnostics
        r['power_diagnostics']=diagnostics(self,r)
        return r


def reviewed_parameters(**overrides):
    values=dict(initial_flux=0,gearbox_efficiency=.9,drivetrain_loss_torque=.1,
                chopper_threshold=500,dc_brake_resistance=330,charger_min_dc_voltage=480,boost_target_voltage=600)
    values.update(overrides)
    return small_hoist(**values)

