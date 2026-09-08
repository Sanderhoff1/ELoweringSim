"""Architecture-level dynamics and controller-facing state regressions."""
from dataclasses import replace
import math
import unittest
from unittest.mock import patch

from simulation.auxiliary import auxiliary_step
from simulation.external_exciter import current
from simulation.external_model import (ExciterSolverError, ExternalLoweringModel,
                                       Kernel, reviewed_parameters)
from simulation.mechanical import MechanicalModel
from simulation.parameters import Parameters


def advance(model, seconds, sample=False):
    rows=[]
    for index in range(round(seconds/.002)):
        model.step(.002)
        if sample and index%5==0:
            rows.append(model.readings())
    return rows if sample else model.readings()


class ExciterArchitectureTests(unittest.TestCase):
    def test_reverse_blocking_reactive_capability_and_physical_limits(self):
        p=reviewed_parameters()
        voltage=200+0j
        for request in (-20+10j,-2-20j,10+20j):
            i,dc_input,loss,limited=current(
                p,voltage,request,1j,1000,True,1000,dc_voltage=600,active_limit=12)
            pac=1.5*(voltage*i.conjugate()).real
            self.assertGreaterEqual(pac,-1e-10)
            self.assertLessEqual(pac,12+1e-9)
            self.assertLessEqual(abs(i)/math.sqrt(2),p.inverter_current_limit+1e-10)
            self.assertLessEqual(abs((i/(voltage/abs(voltage))).imag)/math.sqrt(2),
                                 p.inverter_reactive_current_limit+1e-10)
            self.assertAlmostEqual(dc_input,pac+loss,places=9)
        reactive,_,_,_=current(
            p,voltage,10j,1j,0,True,1000,dc_voltage=600,active_limit=0)
        self.assertEqual((reactive/(voltage/abs(voltage))).real,0)
        self.assertNotEqual(reactive.imag,0)

    def test_virtual_impedance_is_not_converter_heat(self):
        p=reviewed_parameters(inverter_output_resistance=20,
                              inverter_conduction_resistance=.1)
        i,dc_input,loss,_=current(p,100+0j,1+1j,1j,0,True,1000,
                                  dc_voltage=600,active_limit=1000)
        expected=1.5*p.inverter_conduction_resistance*abs(i)**2+p.inverter_idle_loss
        self.assertAlmostEqual(loss,expected,places=10)
        self.assertAlmostEqual(dc_input,1.5*(100*i.conjugate()).real+loss,places=10)

    def test_numerical_failure_is_explicit_not_a_converter_trip(self):
        p=reviewed_parameters()
        kernel=Kernel(p);kernel.supply_limit=1000
        with patch('simulation.external_model._bounded_network_root',return_value=(None,3,1.0)):
            with self.assertRaises(ExciterSolverError):
                kernel.rate((.2+.1j,.1j,100+0j),0,10,0,0,True,True,False,600,'isolated',100)


class AuxiliaryLinkTests(unittest.TestCase):
    def test_finite_capacitor_charge_and_discharge(self):
        c=470e-6
        charged=auxiliary_step(c,0,.01,.5,0)
        self.assertGreater(charged['voltage'],0)
        self.assertAlmostEqual(charged['energy'],.01*charged['source_power'],places=12)
        discharged=auxiliary_step(c,charged['energy'],.001,0,charged['energy']/2/.001)
        self.assertAlmostEqual(discharged['energy'],charged['energy']/2,places=10)

    def test_no_battery_means_no_hidden_high_voltage_source(self):
        m=ExternalLoweringModel(reviewed_parameters(battery_initial_soc=0))
        r=advance(m,.2)
        self.assertLess(r['aux_voltage'],1e-12)
        self.assertEqual(r['boost_power'],0)
        self.assertEqual(r['inverter_dc_power'],0)
        self.assertEqual(r['flux_magnitude'],0)


class SwitchingAndStartupTests(unittest.TestCase):
    def test_main_link_isolated_during_field_build_then_precharged(self):
        m=ExternalLoweringModel()
        before=advance(m,.8)
        self.assertEqual(before['main_dc_connection'],'ISOLATED')
        self.assertEqual(before['dc_energy'],0)
        rows=advance(m,1.2,True)
        states=[r['main_dc_connection'] for r in rows]
        self.assertIn('PRECHARGE',states)
        self.assertEqual(states[-1],'MAIN')
        self.assertGreater(rows[-1]['dc_precharge_loss_energy'],0)
        self.assertLess(abs(rows[-1]['energy_residual']),.002)

    def test_residual_start_releases_for_rotation(self):
        m=ExternalLoweringModel(reviewed_parameters(initial_flux=.005))
        m.excitation_mode='capacitor';m.start_mode='residual';m.reset()
        m.step()
        self.assertTrue(m.brake_released)
        self.assertIsNotNone(m.release_time)
        self.assertIn('RESIDUAL',m.startup_status)

    def test_precharged_bank_has_defined_switch_state_and_finite_source(self):
        p=reviewed_parameters(precharge_voltage=120)
        m=ExternalLoweringModel(p)
        m.excitation_mode='capacitor';m.start_mode='precharged';m.reset()
        r=m.readings()
        self.assertTrue(r['k_cap'])
        self.assertFalse(r['k_exc'])
        self.assertEqual(r['main_dc_connection'],'ISOLATED')
        self.assertGreater(r['capacitor_energy'],0)
        self.assertAlmostEqual(p.battery_capacity_wh*3600-m.electrical.battery_energy,
            r['capacitor_energy']+m.electrical.precharge_loss_energy,places=8)
        self.assertLess(abs(r['energy_residual']),1e-9)

    def test_brake_command_delays_are_distinct_from_physical_state(self):
        p=replace(Parameters(),brake_release_delay=.05,brake_application_delay=.03,
                  brake_response=0,brake_torque=1000)
        m=MechanicalModel(p)
        m.brake_released=True
        for _ in range(4):m.step(.01)
        self.assertFalse(m.readings()['brake_physically_released'])
        m.step(.011)
        self.assertTrue(m.readings()['brake_physically_released'])
        m.brake_released=False
        for _ in range(2):m.step(.01)
        self.assertTrue(m.readings()['brake_physically_released'])
        m.step(.011)
        self.assertEqual(m.readings()['brake_physical_state'],'APPLIED')


class WholeArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=ExternalLoweringModel()
        cls.rows=advance(cls.model,2.2,True)

    def test_standstill_to_generating_lowering_sequence(self):
        rows=self.rows
        self.assertTrue(any(r['auxiliary_hv_ready'] for r in rows))
        self.assertTrue(any(r['brake_physically_released'] for r in rows))
        self.assertTrue(any(r['motor_mode']=='GENERATOR' or r['motor_mode']=='GENERATING' for r in rows))
        self.assertTrue(any(r['rectifier_power']>0 for r in rows))
        self.assertTrue(any(r['chopper_active'] for r in rows))
        after_release=[r for r in rows if r['brake_command']=='RELEASE']
        self.assertTrue(after_release)
        self.assertLessEqual(max(r['inverter_real_power'] for r in after_release),
                             self.model.parameters.exciter_run_active_limit+1e-6)
        final=rows[-1]
        self.assertEqual(final['main_dc_connection'],'MAIN')
        self.assertGreater(final['dc_brake_power'],100)
        self.assertLess(abs(final['acceleration']),.02)
        self.assertLess(abs(final['energy_residual']),.002)

    def test_stop_command_applies_brake_and_stops(self):
        m=self.model
        m.controls.stop=True
        r=advance(m,1.0)
        self.assertEqual(r['brake_command'],'APPLY')
        self.assertEqual(r['brake_physical_state'],'APPLIED')
        self.assertLess(abs(r['velocity']),1e-5)


if __name__=='__main__':
    unittest.main()
