"""Couple the dynamic electrical circuit to the existing lowering mechanics."""
from dataclasses import replace
import math
from .mechanical import MechanicalModel, PHYSICS_DT
from . import dynamic_induction as electrical


class DynamicLoweringModel(MechanicalModel):
    def __init__(self, parameters=None):
        self.rectifier_enabled = False
        self.chopper_active = False
        self.chopper_enabled = True
        self.dc_exciter = False
        super().__init__(parameters)
        self.motor_connected = self.ideal_excitation = self.capacitors_enabled = True
        self.reset()

    def reset(self):
        super().reset()
        self.state.omega = self.parameters.initial_shaft_rpm*2*math.pi/60
        self.electrical = electrical.initial_state(self.parameters)
        self.mechanical_dissipation = 0.0
        self.initial_energy = self.total_energy()

    def total_energy(self):
        p, s, e = self.parameters, self.state, self.electrical
        magnetic, capacitor = electrical.stored_energy(p, (e.stator_flux,e.rotor_flux,e.voltage), self.capacitors_enabled, self.motor_connected)
        dc = 0.5*p.dc_capacitance*1e-6*e.dc_voltage**2 if self.rectifier_enabled else 0.0
        return magnetic+capacitor+dc+0.5*(p.inertia+p.mass*p.radius**2)*s.omega**2-p.mass*p.gravity*s.position

    def electrical_readings(self, omega=None):
        return electrical.readings(self.parameters, self.electrical,
            self.state.omega if omega is None else omega, self.inverter_enabled,
            self.capacitors_enabled, self.motor_connected, self.rectifier_enabled,
            self.chopper_active,self.dc_exciter,self.chopper_enabled)

    def step(self, dt=PHYSICS_DT):
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("dt must be finite and positive")
        p = self.parameters
        # Bounded substeps independent of wall time and rendering. Resolve both
        # electrical rotation and the fastest winding/capacitor time scales.
        rate = max(p.stator_resistance/p.stator_leakage,
                   p.rotor_resistance/p.rotor_leakage,
                   p.pole_pairs*abs(self.state.omega), 1/p.excitation_response,
                   2*math.pi*p.supply_frequency)
        ceq = 3*p.capacitor_capacitance*1e-6 if self.capacitors_enabled else 0.0
        if ceq:
            rate = max(rate, 1/math.sqrt(ceq*min(p.stator_leakage,p.rotor_leakage)),
                       1/(p.ac_load_resistance*ceq))
        if self.rectifier_enabled:
            rate = max(rate, 1/(p.rectifier_resistance*p.dc_capacitance*1e-6),
                       1/(p.dc_brake_resistance*p.dc_capacitance*1e-6),
                       2*electrical.K**2/(3*ceq*p.rectifier_resistance) if ceq else p.rectifier_resistance/p.stator_leakage)
        if not ceq and not self.inverter_enabled and not self.rectifier_enabled:
            rate = max(rate, p.ac_load_resistance/p.stator_leakage)
        if self.chopper_active:
            rate=max(rate,1/p.chopper_response)
        if self.dc_exciter and ceq:
            rate=max(rate,1/(ceq*p.inverter_output_resistance))
        # RK4 resolves the passive RC charging pole with at least two steps
        # per fastest time constant; retain the earlier bound in AC mode.
        rate_fraction = 0.5 if self.rectifier_enabled else 0.1
        count = max(1, math.ceil(dt/min(electrical.ELECTRICAL_DT, rate_fraction/rate)))
        if count > 20000:
            raise ValueError("Selected electrical parameters require too many substeps; use less extreme values.")
        h = dt/count
        for _ in range(count):
            self._substep(h)

    def _substep(self, h):
        p, s = self.parameters, self.state
        target = 0.0 if self.brake_released else 1.0
        initial_brake = s.brake_fraction
        def fraction(t):
            return target if p.brake_response == 0 else target+(initial_brake-target)*math.exp(-t/p.brake_response)
        s.brake_fraction = fraction(h/2)
        # Midpoint speed prediction respects the mechanical brake's stop rule.
        before = replace(s)
        old_torque = self.electrical_readings()['motor_torque']
        if not s.grounded:
            self._motion(h/2, old_torque)
        mid_speed = self.state.omega
        self.state = replace(before)
        torque = electrical.advance(p, self.electrical, h, mid_speed,
            self.inverter_enabled, self.capacitors_enabled, self.motor_connected, self.rectifier_enabled,
            self.chopper_active,self.dc_exciter,self.chopper_enabled)
        if before.grounded:
            self.state.time += h
        else:
            self._motion(h, torque)
            if self.state.position >= p.crane_height:
                low, high = 0.0, h
                for _ in range(32):
                    mid = (low+high)/2
                    self.state = replace(before)
                    self._motion(mid, torque)
                    if self.state.position < p.crane_height:
                        low = mid
                    else:
                        high = mid
                self.state = replace(before)
                self._motion(high, torque)
                s = self.state
                s.impact_speed = p.radius*s.omega
                s.impact_energy = 0.5*(p.inertia+p.mass*p.radius**2)*s.omega**2
                s.impact_time = before.time+high
                s.position = p.crane_height
                s.angle = p.crane_height/p.radius
                s.omega = 0.0
                s.grounded = True
                s.time = before.time+h
            # Mechanical work balance determines dissipated brake/friction
            # work without pretending these are constant over a substep.
            j = p.inertia+p.mass*p.radius**2
            movement = self.state.angle-before.angle
            lost = (p.mass*p.gravity*p.radius+torque)*movement
            lost -= 0.5*j*(self.state.omega**2-before.omega**2)
            self.mechanical_dissipation += lost
        self.state.brake_fraction = fraction(h)

    def readings(self):
        r = super().readings()
        r['energy_residual'] = (self.total_energy()-self.initial_energy
            +self.electrical.load_energy+self.electrical.copper_energy
            +self.electrical.dc_brake_energy+self.electrical.rectifier_loss_energy
            +self.electrical.inverter_loss_energy
            +self.mechanical_dissipation-self.electrical.source_energy)
        return r
