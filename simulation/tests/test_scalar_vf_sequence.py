"""Scalar V/f commands and the explicit automatic sequence."""
import math
import unittest

from simulation.external_model import ExternalLoweringModel, reviewed_parameters
from simulation.converter_controls import chopper_target
from simulation.scalar_vf import (ScalarVFState, base_flux, base_voltage,
                                  stator_drop_compensation, step)


class ScalarVFTests(unittest.TestCase):
    def test_flux_target_and_telemetry_use_same_peak_phase_quantity(self):
        p=reviewed_parameters()
        expected=min(p.exciter_flux_target,
                     math.sqrt(2/3)*p.volts_per_hz/(2*math.pi))
        self.assertAlmostEqual(base_flux(p),expected)
        model=ExternalLoweringModel(p)
        model.electrical.stator_flux=.8+.2j
        model.electrical.rotor_flux=.6-.1j
        magnetizing=model.kernel.currents(model.electrical.stator_flux,
                                          model.electrical.rotor_flux)[2]
        self.assertAlmostEqual(model.readings()['flux_magnitude'],
                               abs(magnetizing))

    def test_frequency_ramps_and_generating_stator_resistance_compensation(self):
        p = reviewed_parameters()
        state = ScalarVFState(frequency_command=20, flux_target=base_flux(p))
        flux=complex(base_flux(p),0)
        # Induced voltage is +j relative to flux. Generating active current is
        # negative on that axis; the signed Rs correction must therefore reduce
        # rather than boost the requested terminal voltage.
        generating_current=-1j*math.sqrt(2)*.5
        step(p,state,.01,20,base_flux(p),.5,p.boost_target_voltage,True,
             generating_current,flux,0)
        expected=(base_voltage(p,state.frequency_command)
                  -math.sqrt(3)*p.stator_resistance*.5)
        self.assertAlmostEqual(state.voltage_command, expected)
        self.assertLess(state.resistive_compensation,0)
        prior=state.frequency_command
        step(p, state, .1, 0, 0, 0, p.boost_target_voltage)
        self.assertAlmostEqual(state.frequency_command,
                               prior-p.frequency_decel_rate*.1)

    def test_rs_compensation_uses_phase_not_current_magnitude(self):
        p=reviewed_parameters();flux=1+0j;amplitude=math.sqrt(2)*2
        motoring=stator_drop_compensation(p,1j*amplitude,flux)
        generating=stator_drop_compensation(p,-1j*amplitude,flux)
        reactive=stator_drop_compensation(p,amplitude+0j,flux)
        self.assertAlmostEqual(motoring,math.sqrt(3)*p.stator_resistance*2)
        self.assertAlmostEqual(generating,-motoring)
        self.assertAlmostEqual(reactive,0)

    def test_current_and_flux_measurements_derate_excitation(self):
        p = reviewed_parameters(vf_limit_response=.001)
        state = ScalarVFState(frequency_command=5, flux_target=base_flux(p))
        step(p, state, .01, 5, p.maximum_magnetic_flux,
             p.motor_current_limit_rms*1.2, p.boost_target_voltage)
        self.assertTrue(state.current_limited)
        self.assertTrue(state.flux_limited)
        self.assertLess(state.excitation_scale, 1)
        self.assertEqual(state.flux_target, base_flux(p))
        self.assertLess(state.voltage_command,state.unlimited_voltage_command)

    def test_normal_flux_pi_is_separate_from_overflux_protection(self):
        p=reviewed_parameters(vf_flux_ki=0)
        state=ScalarVFState(frequency_command=20)
        step(p,state,.01,20,.8,1,p.boost_target_voltage)
        self.assertGreater(state.flux_correction,0)
        self.assertFalse(state.flux_limited)
        step(p,state,.01,20,1.05,1,p.boost_target_voltage)
        self.assertLess(state.flux_correction,0)
        self.assertFalse(state.flux_limited)
        step(p,state,.01,20,.96*p.maximum_magnetic_flux,1,p.boost_target_voltage)
        self.assertTrue(state.flux_limited)

    def test_flux_tracks_at_steady_points_and_during_frequency_ramps(self):
        p=reviewed_parameters(frequency_accel_rate=10,frequency_decel_rate=10)
        state=ScalarVFState(frequency_command=5,
                            flux_target=base_flux(p))
        flux=base_flux(p)
        # Independent first-order air-gap-flux surrogate: V/(K f) is the
        # commanded flux. This isolates the controller from plant/topology.
        k=math.sqrt(3/2)*2*math.pi
        maximum=0.0
        settled=[]
        for target in (20,15,10,7.5,5):
            for _ in range(300):
                step(p,state,.002,target,flux,0,p.boost_target_voltage)
                implied=(state.voltage_command/(k*state.frequency_command)
                         if state.frequency_command>.1 else 0.0)
                flux+=(implied-flux)*.002/.04
                maximum=max(maximum,flux)
            settled.append(flux)
        self.assertLess(maximum,p.maximum_magnetic_flux)
        for flux_at_point in settled:
            self.assertAlmostEqual(flux_at_point,base_flux(p),delta=.06)

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
                                sequence_slowdown_2_hold=0,
                                sequence_slowdown_3_hold=0,
                                sequence_slowdown_4_hold=0)
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
        self.assertEqual(model.sequence.target_frequency, 15)
        model.sequence.at_target_elapsed = .01
        model._sequence(.002)
        self.assertEqual(model.sequence.name, 'SLOWDOWN_2')
        self.assertEqual(model.sequence.target_frequency, 10)
        model.sequence.at_target_elapsed = .01
        model._sequence(.002)
        self.assertEqual(model.sequence.name, 'SLOWDOWN_3')
        self.assertEqual(model.sequence.target_frequency, 7.5)
        model.sequence.at_target_elapsed = .01
        model._sequence(.002)
        self.assertEqual(model.sequence.name, 'SLOWDOWN_4')
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

    def test_capacitor_only_chopper_uses_measured_frequency(self):
        model = ExternalLoweringModel(reviewed_parameters())
        model.excitation_mode='capacitor'
        model.reset()
        model.electrical.measured_frequency=10
        model.vf.frequency_command=20
        self.assertEqual(model.chopper_frequency(),10)
        reading=model.readings()
        self.assertAlmostEqual(reading['chopper_target_frequency'],
                               max(0,reading['bus_frequency']))
        self.assertAlmostEqual(reading['chopper_target_voltage'],
                               chopper_target(model.parameters,
                                              max(0,reading['bus_frequency'])))

    def test_normal_target_does_not_replace_hard_overvoltage_limit(self):
        p=reviewed_parameters(chopper_reference_voltage=200,
                              main_dc_max_voltage=650)
        model=ExternalLoweringModel(p)
        model.electrical.dc_energy=.5*model.electrical.capacitance*300**2
        model._sequence(.002)
        self.assertFalse(model.switchgear.fault)
        model.electrical.dc_energy=.5*model.electrical.capacitance*651**2
        model._sequence(.002)
        self.assertEqual(model.switchgear.fault,'MAIN DC OVERVOLTAGE')

    def test_dc_link_state_is_not_artificially_clamped_to_target(self):
        model=ExternalLoweringModel(reviewed_parameters(dc_initial_voltage=450))
        model.controls.main_bypass_command=True
        model.reset()
        model.vf.frequency_command=10
        before=model.electrical.dc_voltage
        self.assertEqual(before,450)
        self.assertEqual(model.readings()['chopper_target_voltage'],200)
        model.step(.002)
        after=model.electrical.dc_voltage
        self.assertNotEqual(after,200)
        self.assertLess(abs(model.readings()['energy_residual']),1e-4)

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

    def test_controller_change_preserves_energy_conservation(self):
        model=ExternalLoweringModel(reviewed_parameters())
        for _ in range(100):
            model.step(.002)
        self.assertLess(abs(model.readings()['energy_residual']),1e-5)


if __name__ == '__main__':
    unittest.main()
