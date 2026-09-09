"""Scalar V/f commands and the explicit automatic sequence."""
import math
import unittest

from simulation.external_model import ExternalLoweringModel, reviewed_parameters
from simulation.scalar_vf import ScalarVFState, base_flux, step


class ScalarVFTests(unittest.TestCase):
    def test_frequency_ramps_and_stator_resistance_compensation(self):
        p = reviewed_parameters()
        state = ScalarVFState()
        step(p, state, .1, 20, 0, 2, p.boost_target_voltage)
        self.assertAlmostEqual(state.frequency_command,
                               p.frequency_accel_rate*.1)
        expected = (p.volts_per_hz*state.frequency_command
                    + math.sqrt(3)*p.stator_resistance*2)
        self.assertAlmostEqual(state.voltage_command, expected)
        step(p, state, .1, 0, 0, 0, p.boost_target_voltage)
        self.assertAlmostEqual(state.frequency_command,
                               p.frequency_accel_rate*.1-p.frequency_decel_rate*.1)

    def test_current_and_flux_measurements_derate_excitation(self):
        p = reviewed_parameters(vf_limit_response=.001)
        state = ScalarVFState(frequency_command=5, flux_target=base_flux(p))
        step(p, state, .01, 5, p.maximum_magnetic_flux,
             p.motor_current_limit_rms*1.2, p.boost_target_voltage)
        self.assertTrue(state.current_limited)
        self.assertTrue(state.flux_limited)
        self.assertLess(state.excitation_scale, 1)
        self.assertLess(state.flux_target, base_flux(p))

    def test_auxiliary_link_is_a_physical_voltage_limit(self):
        p = reviewed_parameters()
        state = ScalarVFState(frequency_command=20)
        step(p, state, .01, 20, 0, 0, 100)
        self.assertLessEqual(state.voltage_command, 100/math.sqrt(2))


class SequenceTests(unittest.TestCase):
    def test_automatic_targets_and_brake_order(self):
        p = reviewed_parameters(sequence_ready_time=0,
                                sequence_normal_hold=0,
                                sequence_slowdown_1_hold=0,
                                sequence_slowdown_2_hold=0)
        model = ExternalLoweringModel(p)
        model.controls.automatic_profile = True
        model.reset()
        model._transition('READY_TO_RELEASE')
        model._sequence(.002)
        self.assertEqual(model.sequence.name, 'BRAKE_RELEASE')
        model._sequence(.002)
        self.assertTrue(model.brake_released)
        model.state.brake_fraction = 0
        model._sequence(.002)
        self.assertEqual(model.sequence.name, 'LOWERING')
        self.assertEqual(model.sequence.target_frequency, 20)
        model.sequence.at_target_elapsed = .01
        model._sequence(.002)
        self.assertEqual(model.sequence.name, 'SLOWDOWN_1')
        self.assertEqual(model.sequence.target_frequency, 10)
        model.sequence.at_target_elapsed = .01
        model._sequence(.002)
        self.assertEqual(model.sequence.name, 'SLOWDOWN_2')
        self.assertEqual(model.sequence.target_frequency, 5)
        model.sequence.at_target_elapsed = .01
        model._sequence(.002)
        self.assertEqual(model.sequence.name, 'BRAKE_APPLY')
        model._sequence(.002)
        self.assertFalse(model.brake_released)
        self.assertTrue(model.switchgear.k_exc)
        model.state.brake_fraction = 1
        model.state.omega = 0
        model._sequence(.002)
        self.assertEqual(model.sequence.name, 'STOPPED')
        self.assertFalse(model.switchgear.k_exc)

    def test_capacitor_only_has_no_frequency_command(self):
        model = ExternalLoweringModel(reviewed_parameters(initial_flux=.005))
        model.excitation_mode = 'capacitor'
        model.start_mode = 'residual'
        model.reset()
        model._sequence(.002)
        reading = model.readings()
        self.assertEqual(model.frequency(), 0)
        self.assertEqual(reading['stator_frequency_command'], 0)
        self.assertFalse(reading['frequency_command_applicable'])

    def test_runaway_fault_commands_brake(self):
        p = reviewed_parameters(runaway_dwell=.004)
        model = ExternalLoweringModel(p)
        model._transition('LOWERING')
        model.brake_released = True
        model.state.omega = 2*p.runaway_speed_limit/p.radius
        for _ in range(3):
            model._sequence(.002)
        self.assertEqual(model.sequence.name, 'FAULT')
        self.assertEqual(model.switchgear.fault, 'RUNAWAY DIAGNOSTIC')
        self.assertFalse(model.brake_released)

    def test_flux_limit_is_a_hardware_fault_in_both_topologies(self):
        p = reviewed_parameters(exciter_flux_target=.09,
                                maximum_magnetic_flux=.1)
        for mode in ('exciter', 'capacitor'):
            model = ExternalLoweringModel(p)
            model.excitation_mode = mode
            model.reset()
            model.electrical.stator_flux = 2+0j
            model.electrical.rotor_flux = 2+0j
            self.assertGreater(abs(model.kernel.currents(
                model.electrical.stator_flux,
                model.electrical.rotor_flux)[2]), p.maximum_magnetic_flux)
            model._sequence(.002)
            self.assertEqual(model.sequence.name, 'FAULT')
            self.assertEqual(model.switchgear.fault, 'MACHINE OVERFLUX')


if __name__ == '__main__':
    unittest.main()
