from dataclasses import replace
import math
import unittest

from simulation.excitation import excitation_readings
from simulation.induction import motor_readings
from simulation.mechanical import MechanicalModel, Playback
from simulation.parameters import Parameters


class ExcitationTests(unittest.TestCase):
    def test_three_phase_magnetizing_demand(self):
        r = excitation_readings(Parameters(), True)
        self.assertAlmostEqual(r['line_voltage'], 40)
        self.assertAlmostEqual(r['inverter_current'], 40/math.sqrt(3)/(2*math.pi*5*0.2))
        self.assertAlmostEqual(r['inverter_reactive_supply'], 40**2/(2*math.pi*5*0.2))
        self.assertEqual(r['inverter_reactive_supply'], r['machine_reactive_demand'])
        self.assertEqual(r['inverter_real_power'], 0)

    def test_fixed_vf_frequency_scaling(self):
        p = Parameters()
        a, b = excitation_readings(p, True), excitation_readings(replace(p, supply_frequency=10), True)
        self.assertAlmostEqual(b['line_voltage'], 2*a['line_voltage'])
        self.assertAlmostEqual(b['inverter_current'], a['inverter_current'])
        self.assertAlmostEqual(b['inverter_reactive_supply'], 2*a['inverter_reactive_supply'])

    def test_voltage_scaling_of_torque_and_var(self):
        p = Parameters()
        a = motor_readings(p, 18, True, True)
        b = motor_readings(replace(p, volts_per_hz=4), 18, True, True)
        self.assertAlmostEqual(b['motor_torque'], a['motor_torque']/4)
        self.assertAlmostEqual(b['inverter_reactive_supply'], a['inverter_reactive_supply']/4)
        self.assertAlmostEqual(b['inverter_current'], a['inverter_current']/2)

    def test_loss_of_excitation_removes_torque_and_power(self):
        for connected, enabled, vf in [(True, False, 8), (False, True, 8), (True, True, 0)]:
            r = motor_readings(Parameters(volts_per_hz=vf), 20, connected, True, enabled)
            for key in ('motor_torque', 'electrical_export', 'rotor_loss', 'inverter_current', 'line_voltage', 'machine_line_current'):
                self.assertEqual(r[key], 0)

    def test_real_reactive_and_apparent_power_balance(self):
        for omega in (0, 10, 5*math.pi, 20, 30):
            r = motor_readings(Parameters(), omega, True, True)
            self.assertAlmostEqual(r['electrical_input'], r['motor_shaft_power']+r['rotor_loss'])
            self.assertAlmostEqual(r['machine_apparent_power'], math.sqrt(3)*r['line_voltage']*r['machine_line_current'])
            self.assertAlmostEqual(r['machine_reactive_demand'], r['inverter_apparent_power'])
        r = motor_readings(Parameters(), 5*math.pi, True, True)
        self.assertEqual(r['electrical_input'], 0)
        self.assertGreater(r['inverter_current'], 0)  # still excited at synchronism

    def test_reference_vf_reproduces_phase2_trajectory(self):
        a, b = MechanicalModel(), MechanicalModel()
        for m in (a, b):
            m.motor_connected = True
            m.brake_released = True
        b.ideal_excitation = True
        for _ in range(1500):
            a.step()
            b.step()
        self.assertEqual(a.state, b.state)
        b.inverter_enabled = False
        self.assertEqual(b.readings()['motor_torque'], 0)
        self.assertGreater(b.readings()['acceleration'], 0)

    def test_playback_independent_excitation(self):
        results = []
        for speed, frames in [(0.05, 1200), (1, 60), (10, 6)]:
            m = MechanicalModel()
            m.motor_connected = m.ideal_excitation = m.brake_released = True
            clock = Playback(m)
            for _ in range(frames):
                clock.advance(1/60, speed)
            results.append((m.state, m.readings()))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], results[2])

    def test_parameter_validation(self):
        for kwargs in (dict(magnetizing_inductance=0), dict(reference_volts_per_hz=0), dict(volts_per_hz=-1)):
            with self.assertRaises(ValueError):
                Parameters(**kwargs)
