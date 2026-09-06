"""Independent sign, energy, equilibrium and integration checks for Phase 2."""
from dataclasses import replace
import math
import unittest

from simulation.induction import motor_readings
from simulation.mechanical import MechanicalModel, Playback
from simulation.parameters import Parameters


class InductionTests(unittest.TestCase):
    def test_synchronous_speed_and_zero_torque(self):
        p = Parameters(supply_frequency=50, pole_pairs=2)
        r = motor_readings(p, 50*math.pi, True)
        self.assertAlmostEqual(r['synchronous_rpm'], 1500)
        self.assertEqual(r['slip'], 0)
        self.assertEqual(r['motor_torque'], 0)

    def test_peak_torque_sign_and_power_balance(self):
        p = Parameters()
        ws = 2*math.pi*p.supply_frequency/p.pole_pairs
        for slip in (-2, -p.peak_slip, -0.05, 0, 0.05, p.peak_slip, 1):
            r = motor_readings(p, ws*(1-slip), True)
            self.assertAlmostEqual(r['electrical_input'], r['motor_shaft_power']+r['rotor_loss'])
            self.assertGreaterEqual(r['rotor_loss'], 0)
            self.assertLessEqual(abs(r['motor_torque']), p.peak_motor_torque+1e-10)
            if abs(slip) == p.peak_slip:
                self.assertAlmostEqual(r['motor_torque'], math.copysign(p.peak_motor_torque, slip))
            if slip < 0:
                self.assertGreater(r['electrical_export'], 0)
                self.assertLess(r['motor_torque'], 0)

    def test_disconnected_is_no_electrical_power(self):
        r = motor_readings(Parameters(), 20, False)
        for name in ('motor_torque', 'electrical_export', 'motor_shaft_power', 'rotor_loss'):
            self.assertEqual(r[name], 0)

    def test_generator_equilibrium_matches_quadratic_solution(self):
        p = Parameters(damping=0, brake_torque=0, crane_height=1000)
        load_torque = p.mass*p.gravity*p.radius
        # Solve 2*Tpeak*z/(1+z²)=load_torque on stable generating branch.
        z = load_torque/(p.peak_motor_torque+math.sqrt(p.peak_motor_torque**2-load_torque**2))
        ws = 2*math.pi*p.supply_frequency/p.pole_pairs
        expected_omega = ws*(1+p.peak_slip*z)
        m = MechanicalModel(p)
        m.motor_connected = True
        m.brake_released = True
        for _ in range(5000):
            m.step()
        self.assertAlmostEqual(m.state.omega, expected_omega, places=8)
        self.assertAlmostEqual(m.readings()['motor_torque'], -load_torque, places=8)
        self.assertEqual(m.readings()['motor_mode'], 'GENERATING')

    def test_motor_torque_is_included_in_static_brake_holding(self):
        p = Parameters(brake_response=0)
        m = MechanicalModel(p)
        m.motor_connected = True
        for _ in range(100):
            m.step()
        self.assertEqual(m.state.position, 0)
        self.assertGreater(m.readings()['rotor_loss'], 0)  # energized at standstill
        m.parameters = replace(p, brake_torque=100)
        m.step()
        self.assertGreater(m.state.position, 0)  # gravity alone is below 100 Nm

    def test_timestep_refinement(self):
        results = []
        for dt in (0.002, 0.001, 0.0005):
            m = MechanicalModel(Parameters(brake_response=0, crane_height=100))
            m.motor_connected = True
            m.brake_released = True
            for _ in range(round(0.5/dt)):
                m.step(dt)
            results.append(m.state.omega)
        self.assertLess(abs(results[0]-results[2]), 0.002)
        self.assertLess(abs(results[1]-results[2]), abs(results[0]-results[2]))

    def test_connected_playback_and_landing(self):
        states = []
        for speed, frames in [(0.05, 2400), (1, 120), (10, 12)]:
            m = MechanicalModel(Parameters(crane_height=1))
            m.motor_connected = True
            m.brake_released = True
            playback = Playback(m)
            for _ in range(frames):
                playback.advance(1/60, speed)
            self.assertTrue(m.state.grounded)
            self.assertEqual(m.state.position, 1)
            states.append(m.state)
        self.assertEqual(states[0], states[1])
        self.assertEqual(states[0], states[2])

    def test_motor_parameter_validation(self):
        for kwargs in (dict(pole_pairs=1.5), dict(peak_slip=0), dict(supply_frequency=0), dict(peak_motor_torque=-1)):
            with self.assertRaises(ValueError):
                Parameters(**kwargs)
