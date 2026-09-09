"""Regressions for passive conduction and explicit topology controls."""
import math
import unittest

from simulation.auxiliary import paths
from simulation.capacitor_rectifier import midpoint_voltage, transfer
from simulation.external_exciter import current as exciter_current
from simulation.external_model import ExternalLoweringModel, reviewed_parameters


class PassiveRectifierTests(unittest.TestCase):
    def test_diode_conducts_without_an_ac_enable_threshold(self):
        for line_voltage in (0.1, 1.0, 125.0, 400.0):
            with self.subTest(line_voltage=line_voltage):
                peak=math.sqrt(2)*line_voltage
                current,power,loss=transfer(line_voltage,0.0,10.0)
                self.assertGreater(current,0.0)
                self.assertGreater(power,0.0)
                self.assertAlmostEqual(power,loss,places=12)
                self.assertEqual(transfer(line_voltage,peak,10.0),(0.0,0.0,0.0))

    def test_empty_dc_capacitor_charges_from_low_frequency_voltage_level(self):
        capacitance=470e-6
        energy=0.0
        midpoint=midpoint_voltage(energy,capacitance,1e-4,125.0,160.0,0.0)
        dc_power=midpoint*transfer(125.0,midpoint,160.0)[0]
        energy+=1e-4*dc_power
        self.assertGreater(midpoint,0.0)
        self.assertGreater(energy,0.0)

    def test_125_v_bus_charges_connected_model_despite_startup_state(self):
        m=ExternalLoweringModel(reviewed_parameters(initial_flux=0,dc_initial_voltage=0))
        m.startup_enabled=False
        m.excitation_mode='capacitor'
        m.start_mode='zero'
        m.controls.main_bypass_command=False
        m.reset()
        m.electrical.voltage=complex(math.sqrt(2/3)*125.0)
        m.initial_energy=m.total_energy()
        before=m.electrical.dc_energy
        m.step(1e-4)
        r=m.readings()
        self.assertEqual(r['main_dc_connection'],'PRECHARGE')
        self.assertGreater(m.electrical.dc_energy,before)
        self.assertGreater(r['rectifier_power'],0.0)


class PhysicalControlTests(unittest.TestCase):
    def test_precharge_resistor_limits_current_and_dissipates_heat(self):
        p=reviewed_parameters()
        line_voltage=125.0
        main=transfer(line_voltage,0.0,p.rectifier_resistance)
        precharge=transfer(line_voltage,0.0,p.rectifier_resistance+p.dc_precharge_resistance)
        self.assertLess(precharge[0],main[0])
        resistor_heat=precharge[2]*p.dc_precharge_resistance/(p.rectifier_resistance+p.dc_precharge_resistance)
        self.assertGreater(resistor_heat,0.0)

    def test_main_bypass_changes_topology_only_from_its_command(self):
        m=ExternalLoweringModel()
        m.controls.main_bypass_command=False
        m.step(1e-4)
        self.assertTrue(m.switchgear.k_precharge)
        self.assertFalse(m.switchgear.k_main)
        m.controls.main_bypass_command=True
        m.step(1e-4)
        self.assertFalse(m.switchgear.k_precharge)
        self.assertTrue(m.switchgear.k_main)

    def test_chopper_uses_actual_dc_voltage_while_main_contactor_is_open(self):
        m=ExternalLoweringModel(reviewed_parameters(dc_initial_voltage=550,chopper_threshold=500))
        m.inverter_enabled=False
        m.controls.main_bypass_command=False
        before=m.electrical.dc_energy
        m.step(.01)
        r=m.readings()
        self.assertFalse(r['k_main'])
        self.assertGreater(r['chopper_duty'],0.0)
        self.assertGreater(r['dc_brake_power'],0.0)
        self.assertLess(m.electrical.dc_energy,before)

    def test_exciter_hv_ready_interlock_and_reverse_power_block(self):
        p=reviewed_parameters()
        m=ExternalLoweringModel(p)
        m.electrical.aux_energy=.5*m.electrical.aux_capacitance*(p.aux_ready_voltage-.1)**2
        self.assertFalse(m.excitation_active())
        m.electrical.aux_energy=.5*m.electrical.aux_capacitance*(p.aux_ready_voltage+.1)**2
        m._transition('EXCITATION_BUILD');m.switchgear.k_exc=True
        self.assertTrue(m.excitation_active())
        for request in (-10+10j,-1-10j,10j):
            phase_current,dc_input,loss,_=exciter_current(
                p,200+0j,request,1j,1000,True,1000,dc_voltage=600,active_limit=0)
            ac_power=1.5*(complex(200)*phase_current.conjugate()).real
            self.assertGreaterEqual(ac_power,-1e-10)
            self.assertAlmostEqual(dc_input,ac_power+loss,places=9)
        reactive,_,_,_=exciter_current(
            p,200+0j,10j,1j,0,True,1000,dc_voltage=600,active_limit=0)
        self.assertNotEqual(reactive.imag,0.0)

    def test_charger_minimum_input_voltage_is_converter_operating_range(self):
        p=reviewed_parameters(charger_min_dc_voltage=480,battery_initial_soc=50)
        energy=.5*p.battery_capacity_wh*3600
        below=paths(p,energy,0,479.9,1e-3,True)
        above=paths(p,energy,0,480.0,1e-3,True)
        self.assertEqual(below['charger_input'],0.0)
        self.assertGreater(above['charger_input'],0.0)

    def test_k_cap_and_k_exc_are_mutually_selected_physical_states(self):
        m=ExternalLoweringModel()
        exciter=m.readings()
        self.assertFalse(exciter['k_cap'])
        self.assertFalse(exciter['k_exc'])  # AUXILIARY_START keeps the AC contactor open.
        self.assertEqual(exciter['capacitor_line_current'],0.0)
        m.electrical.aux_energy=.5*m.electrical.aux_capacitance*(m.parameters.aux_ready_voltage+.1)**2
        m.step(1e-4)
        self.assertTrue(m.readings()['k_exc'])
        m.excitation_mode='capacitor'
        m.start_mode='residual'
        m.reset()
        capacitor=m.readings()
        self.assertTrue(capacitor['k_cap'])
        self.assertFalse(capacitor['k_exc'])
        self.assertEqual(capacitor['inverter_current'],0.0)

    def test_brake_command_and_physical_state_are_distinct(self):
        m=ExternalLoweringModel(reviewed_parameters(brake_release_delay=.05,brake_response=0))
        m.startup_enabled=False
        m.reset()
        m.brake_released=True
        m.step(.01)
        r=m.readings()
        self.assertEqual(r['brake_command'],'RELEASE')
        self.assertEqual(r['brake_physical_state'],'APPLIED')


if __name__=='__main__':
    unittest.main()
