import math
import unittest
from simulation.parameters import Parameters
from simulation.mechanical import MechanicalModel, Playback


class MechanicsTests(unittest.TestCase):
    def model(self, **kwargs):
        return MechanicalModel(Parameters(**dict(dict(inertia=0, damping=0, brake_torque=0, brake_response=0, crane_height=100), **kwargs)))

    def advance(self, model, seconds):
        for _ in range(round(seconds / 0.002)):
            model.step()

    def test_free_fall(self):
        m = self.model()
        self.advance(m, 1)
        self.assertAlmostEqual(m.state.position, 4.905, places=10)
        self.assertAlmostEqual(m.readings()['velocity'], 9.81, places=10)
        self.assertAlmostEqual(m.readings()['kinetic_energy'] + m.readings()['potential_energy'], 0, places=8)

    def test_brake_holds(self):
        m = self.model(brake_torque=150)
        self.advance(m, 2)
        self.assertEqual(m.state.position, 0)
        self.assertEqual(m.readings()['acceleration'], 0)

    def test_partial_brake(self):
        m = self.model(brake_torque=49.05)
        self.advance(m, 1)
        self.assertAlmostEqual(m.readings()['velocity'], 4.905, places=10)
        self.assertAlmostEqual(m.state.position, 2.4525, places=10)

    def test_stop_without_reversal(self):
        m = self.model(brake_torque=150)
        m.state.omega = 20  # initial load speed 2 m/s
        self.advance(m, 1)
        self.assertEqual(m.state.omega, 0)
        self.assertAlmostEqual(m.state.position, 2**2/(2*5.19), places=10)

    def test_inertia_and_viscous_solution(self):
        m = self.model(inertia=1, damping=0.2)
        self.advance(m, 2)
        p = m.parameters
        j = p.inertia + p.mass*p.radius**2
        terminal = p.mass*p.gravity*p.radius/p.damping
        self.assertAlmostEqual(m.state.omega, terminal*(1-math.exp(-p.damping*2/j)), places=9)
        self.assertAlmostEqual(m.state.angle, terminal*(2-j/p.damping*(1-math.exp(-p.damping*2/j))), places=9)

    def test_playback_speed_independence(self):
        results = []
        for speed, fps in [(0.05, 30), (0.1, 60), (1, 50), (10, 100)]:
            m = self.model()
            clock = Playback(m)
            for _ in range(round(fps/speed)):
                clock.advance(1/fps, speed)
            results.append(m.state)
        for state in results:
            self.assertEqual(state, results[0])

    def test_release_and_reapply(self):
        m = self.model(brake_torque=150)
        m.brake_released = True
        self.advance(m, 0.1)
        self.assertAlmostEqual(m.readings()['velocity'], 0.981)
        m.brake_released = False
        self.advance(m, 1)
        self.assertEqual(m.state.omega, 0)

    def test_reject_invalid_inputs(self):
        for kwargs in [dict(mass=0), dict(radius=0), dict(damping=-1), dict(gravity=float('nan'))]:
            with self.assertRaises(ValueError):
                Parameters(**kwargs)

    def test_brake_response(self):
        m = self.model(brake_response=0.3, brake_torque=150)
        m.brake_released = True
        self.advance(m, 0.3)
        self.assertAlmostEqual(m.state.brake_fraction, math.exp(-1), places=12)
        self.assertGreater(m.state.position, 0)
        m.brake_released = False
        self.advance(m, 0.3)
        self.assertAlmostEqual(m.state.brake_fraction, 1-(1-math.exp(-1))*math.exp(-1), places=12)

    def test_ground_impact_and_hold(self):
        m = self.model(crane_height=1)
        self.advance(m, 1)
        self.assertTrue(m.state.grounded)
        self.assertEqual(m.state.position, 1)
        self.assertEqual(m.state.omega, 0)
        self.assertAlmostEqual(m.state.impact_speed, math.sqrt(2*9.81), places=9)
        self.assertAlmostEqual(m.state.impact_time, math.sqrt(2/9.81), places=9)
        self.assertAlmostEqual(m.state.impact_energy, 981, places=8)
        self.assertEqual(m.readings()['acceleration'], 0)
        self.advance(m, 2)
        self.assertEqual(m.state.position, 1)
        m.reset()
        self.assertFalse(m.state.grounded)

    def test_dynamic_brake_stops_moving_load(self):
        m = self.model(brake_torque=150, brake_response=0.3)
        m.state.brake_fraction = 0
        m.state.omega = 20
        self.advance(m, 3)
        self.assertEqual(m.state.omega, 0)
        self.assertGreater(m.state.position, 2**2/(2*5.19))
        self.assertFalse(m.state.grounded)

    def test_dynamic_playback_independence(self):
        states = []
        for speed, frames in [(0.05, 1200), (1, 60), (10, 6)]:
            m = self.model(brake_torque=150, brake_response=0.3, crane_height=1)
            m.brake_released = True
            clock = Playback(m)
            for _ in range(frames):
                clock.advance(1/60, speed)
            states.append(m.state)
        self.assertEqual(states[0], states[1])
        self.assertEqual(states[0], states[2])


if __name__ == '__main__':
    unittest.main()
