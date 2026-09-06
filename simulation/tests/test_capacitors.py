from dataclasses import replace
import math
import unittest

from simulation.excitation import excitation_readings
from simulation.induction import motor_readings
from simulation.mechanical import MechanicalModel, Playback
from simulation.parameters import Parameters


class CapacitorTests(unittest.TestCase):
    def test_delta_bank_formula_and_current(self):
        p = Parameters()
        r = excitation_readings(p, True, True)
        expected = 3*40**2*(2*math.pi*5)*0.001
        self.assertAlmostEqual(r['capacitor_reactive_supply'], expected)
        self.assertAlmostEqual(r['capacitor_branch_current'], 40*(2*math.pi*5)*0.001)
        self.assertAlmostEqual(r['capacitor_line_current'], math.sqrt(3)*r['capacitor_branch_current'])
        self.assertAlmostEqual(r['capacitor_reactive_supply'], math.sqrt(3)*40*r['capacitor_line_current'])
        self.assertAlmostEqual(r['inverter_reactive_supply']+r['capacitor_reactive_supply'], r['machine_reactive_demand'])

    def test_zero_and_disconnected_bank_reproduce_phase3(self):
        p = Parameters()
        a = excitation_readings(p, True, False)
        b = excitation_readings(replace(p, capacitor_capacitance=0), True, True)
        self.assertEqual(a, b)
        self.assertEqual(a['inverter_reactive_supply'], a['machine_reactive_demand'])

    def test_exact_and_excess_compensation(self):
        p = Parameters()
        matching = 1e6/(3*(2*math.pi*5)**2*0.2)
        r = excitation_readings(replace(p, capacitor_capacitance=matching), True, True)
        self.assertAlmostEqual(r['inverter_current'], 0, places=12)
        self.assertAlmostEqual(r['compensation_fraction'], 1)
        r = excitation_readings(replace(p, capacitor_capacitance=2*matching), True, True)
        self.assertAlmostEqual(r['inverter_reactive_supply'], -r['machine_reactive_demand'])
        self.assertGreater(r['inverter_current'], 0)
        self.assertGreater(r['inverter_apparent_power'], 0)

    def test_frequency_and_voltage_scaling(self):
        p = Parameters()
        a = excitation_readings(p, True, True)
        b = excitation_readings(replace(p, supply_frequency=10), True, True)
        self.assertAlmostEqual(b['capacitor_reactive_supply'], 8*a['capacitor_reactive_supply'])
        self.assertAlmostEqual(b['machine_reactive_demand'], 2*a['machine_reactive_demand'])
        c = excitation_readings(replace(p, volts_per_hz=4), True, True)
        self.assertAlmostEqual(c['capacitor_reactive_supply'], a['capacitor_reactive_supply']/4)

    def test_no_self_excitation_is_explicit(self):
        r = motor_readings(Parameters(), 50, True, True, False, True)
        for key in ('capacitor_reactive_supply', 'capacitor_line_current', 'motor_torque', 'line_voltage'):
            self.assertEqual(r[key], 0)

    def test_capacitors_do_not_change_mechanics_or_real_power(self):
        a, b = MechanicalModel(), MechanicalModel()
        for m in (a, b):
            m.motor_connected = m.ideal_excitation = m.brake_released = True
        b.capacitors_enabled = True
        for _ in range(1500):
            a.step()
            b.step()
        self.assertEqual(a.state, b.state)
        for key in ('motor_torque', 'electrical_export', 'rotor_loss', 'machine_line_current'):
            self.assertEqual(a.readings()[key], b.readings()[key])
        self.assertLess(b.readings()['inverter_current'], a.readings()['inverter_current'])

    def test_playback_and_capacitance_validation(self):
        results = []
        for speed, frames in [(0.05, 1200), (1, 60), (10, 6)]:
            m = MechanicalModel()
            m.motor_connected = m.ideal_excitation = m.capacitors_enabled = m.brake_released = True
            clock = Playback(m)
            for _ in range(frames):
                clock.advance(1/60, speed)
            results.append((m.state, m.readings()))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], results[2])
        for value in (-1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                Parameters(capacitor_capacitance=value)
