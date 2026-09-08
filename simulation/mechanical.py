"""Positive shaft rotation and load displacement both mean lowering."""
from dataclasses import dataclass, replace
import math
from .parameters import Parameters
from .induction import motor_readings

PHYSICS_DT = 0.002  # numerical setting, seconds; independent of playback/rendering


@dataclass
class State:
    time: float = 0.0
    position: float = 0.0
    angle: float = 0.0
    omega: float = 0.0
    brake_fraction: float = 1.0
    brake_command_released: bool = False
    brake_delay_remaining: float = 0.0
    brake_motion_target: float = 1.0
    grounded: bool = False
    impact_speed: float = 0.0
    impact_energy: float = 0.0
    impact_time: float = 0.0


class MechanicalModel:
    def __init__(self, parameters=None):
        self.parameters = parameters or Parameters()
        self.state = State()
        self.brake_released = False
        self.motor_connected = False  # UI explicitly connects Phase 2 by default.
        self.ideal_excitation = False  # Retain standalone Phase 2 comparisons.
        self.inverter_enabled = True
        self.capacitors_enabled = False

    def electrical_readings(self, omega=None):
        return motor_readings(self.parameters, self.state.omega if omega is None else omega,
                              self.motor_connected, self.ideal_excitation, self.inverter_enabled,
                              self.capacitors_enabled)

    def reset(self):
        target = 0.0 if self.brake_released else 1.0
        self.state = State(brake_fraction=target,
                           brake_command_released=self.brake_released,
                           brake_motion_target=target)

    def _prepare_brake(self, dt):
        """Advance command delay and return the physical actuator target.

        ``brake_released`` is the controller/operator command.  The stored
        fraction and motion target are the distinct physical brake state.
        """
        p, s = self.parameters, self.state
        if self.brake_released != s.brake_command_released:
            s.brake_command_released = self.brake_released
            s.brake_delay_remaining = (p.brake_release_delay if self.brake_released
                                       else p.brake_application_delay)
        if s.brake_delay_remaining > 0:
            s.brake_delay_remaining = max(0.0, s.brake_delay_remaining-dt)
            if s.brake_delay_remaining > 0:
                return s.brake_motion_target
        s.brake_motion_target = 0.0 if s.brake_command_released else 1.0
        return s.brake_motion_target

    def brake_capacity(self):
        fraction = (0.0 if self.brake_released else 1.0) if self.parameters.brake_response == 0 else self.state.brake_fraction
        return self.parameters.brake_torque * fraction

    def effective_radius(self, position=None):
        """Single radius/ratio today; future radius laws belong at this interface.

        A variable-radius implementation must also account for variable reflected
        inertia. This rigid model does not predict peak rope/structural forces.
        """
        return self.parameters.radius

    def gear_loss_torque(self):
        p=self.parameters
        return (1-p.gearbox_efficiency)*p.mass*p.gravity*self.effective_radius()

    def _drive(self, motor_torque=None):
        p, s = self.parameters, self.state
        if motor_torque is None:
            motor_torque = self.electrical_readings()['motor_torque']
        gravity_torque = p.mass * p.gravity * p.radius + motor_torque
        brake = self.brake_capacity()+self.gear_loss_torque()+p.drivetrain_loss_torque
        if s.omega == 0.0:
            return max(0.0, gravity_torque - brake)
        return gravity_torque - math.copysign(brake, s.omega)

    def step(self, dt=PHYSICS_DT):
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("dt must be finite and positive")
        p, s = self.parameters, self.state
        target = self._prepare_brake(dt)
        initial = s.brake_fraction
        def fraction(elapsed):
            return target if p.brake_response == 0 else target + (initial-target)*math.exp(-elapsed/p.brake_response)
        # Exact actuator response; midpoint capacity for this bounded motion step.
        s.brake_fraction = fraction(dt/2)
        if s.grounded:
            s.time += dt
        else:
            before = replace(s)
            # Explicit midpoint coupling: predict half-step speed with the
            # initial torque, then integrate using torque at that speed.
            torque = self.electrical_readings()['motor_torque']
            if self.motor_connected:
                self._motion(dt/2, torque)
                torque = self.electrical_readings()['motor_torque']
                self.state = replace(before)
            self._motion(dt, torque)
            if self.state.position >= p.crane_height:
                low, high = 0.0, dt
                for _ in range(40):
                    middle = (low+high)/2
                    self.state = replace(before)
                    self._motion(middle, torque)
                    if self.state.position < p.crane_height:
                        low = middle
                    else:
                        high = middle
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
                s.time = before.time+dt
        self.state.brake_fraction = fraction(dt)

    def _motion(self, dt, motor_torque=0.0):
        p, s = self.parameters, self.state
        inertia = p.inertia + p.mass * p.radius**2
        drive, w0 = self._drive(motor_torque), s.omega
        # Exact integration for constant inputs over this step. Split at a stop
        # so Coulomb friction cannot spuriously reverse the load.
        duration = dt
        if w0 * drive < 0:
            if p.damping:
                stop = math.log1p(-p.damping * w0 / drive) * inertia / p.damping
            else:
                stop = -w0 * inertia / drive
            duration = min(dt, stop)
        if p.damping:
            k = p.damping / inertia
            x = k * duration
            decay_integral = -math.expm1(-x) / k
            # Stable even when damping approaches zero.
            force_integral = (duration**2 * (0.5 - x / 6 + x*x / 24)
                              if abs(x) < 1e-4 else (duration - decay_integral) / k)
            displacement = w0 * decay_integral + drive / inertia * force_integral
            w1 = w0 * math.exp(-x) + drive / inertia * decay_integral
        else:
            w1 = w0 + drive / inertia * duration
            displacement = w0 * duration + 0.5 * drive / inertia * duration**2
        s.angle += displacement
        s.position += p.radius * displacement
        s.omega = w1 if duration == dt else 0.0
        s.time += duration
        if duration < dt:
            self._motion(dt - duration, motor_torque)

    def readings(self):
        p, s = self.parameters, self.state
        velocity = p.radius * s.omega
        acceleration = p.radius * (self._drive() - p.damping * s.omega) / (p.inertia + p.mass*p.radius**2)
        if s.grounded:
            acceleration = 0.0
        brake = self.brake_capacity()
        return dict(position=s.position, velocity=velocity, acceleration=acceleration,
                    clearance=max(0.0, p.crane_height-s.position), brake_capacity=brake,
                    brake_command='RELEASE' if self.brake_released else 'APPLY',
                    brake_physical_state=('RELEASED' if s.brake_fraction <= 0.01 else
                                          'APPLIED' if s.brake_fraction >= 0.99 else 'MOVING'),
                    brake_physically_released=s.brake_fraction <= 0.01,
                    brake_delay_remaining=s.brake_delay_remaining,
                    angle=s.angle, omega=s.omega, rpm=s.omega*60/(2*math.pi),
                    potential_energy=-p.mass*p.gravity*s.position,
                    kinetic_energy=0.5*(p.inertia+p.mass*p.radius**2)*s.omega**2,
                    gravity_power=p.mass*p.gravity*velocity,
                    brake_power=brake*abs(s.omega), friction_power=p.damping*s.omega**2,
                    gear_power=self.gear_loss_torque()*abs(s.omega),
                    drivetrain_power=p.drivetrain_loss_torque*abs(s.omega),
                    **self.electrical_readings())


class Playback:
    """Accumulate scaled wall time; never vary the physics step or discard debt."""
    def __init__(self, model):
        self.model = model
        self.pending = 0.0

    def advance(self, wall_seconds, speed, after_step=None, max_steps=2000):
        self.pending += max(0, wall_seconds) * speed
        count = min(max_steps, int((self.pending + 1e-12) / PHYSICS_DT))
        for _ in range(count):
            self.model.step()
            if after_step:
                after_step()
        self.pending = max(0.0, self.pending - count * PHYSICS_DT)
