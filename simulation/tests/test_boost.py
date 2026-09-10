import random
import unittest

from simulation.boost import support
from simulation.parameters import Parameters
from simulation.dynamic_model import DynamicLoweringModel
from simulation.visual_state import energy_budget


class BoostTests(unittest.TestCase):
    def test_power_current_limits_and_efficiency(self):
        p=Parameters()
        rng=random.Random(24)
        for _ in range(100):
            r=support(p,rng.uniform(0,1000),rng.uniform(0,10),True)
            self.assertGreaterEqual(r['current'],0)
            self.assertLessEqual(r['current'],p.boost_output_current_limit)
            self.assertLessEqual(r['battery_power'],p.boost_input_power_limit+1e-9)
            self.assertAlmostEqual(r['battery_power'],r['output_power']+r['loss'])
            self.assertAlmostEqual(r['battery_current']*24,r['battery_power'])

    def test_standby_reverse_block_and_recovery(self):
        p=Parameters()
        r=support(p,600,1,True)
        self.assertEqual(r['output_power'],0)
        self.assertEqual(r['battery_power'],0)
        self.assertEqual(r['status'],'STANDBY')
        self.assertLess(r['derivative'],0)
        self.assertGreater(support(p,300,0,True)['derivative'],0)
        self.assertEqual(support(p,300,1,False)['battery_power'],0)

    def test_empty_bus_charges_without_brake_heat(self):
        p=Parameters(initial_flux=0,dc_initial_voltage=0,precharge_voltage=0,boost_target_voltage=100,
                     chopper_min_operating_voltage=200,
                     dc_capacitance=1000,boost_input_power_limit=20)
        m=DynamicLoweringModel(p)
        m.rectifier_enabled=m.chopper_active=m.boost_enabled=True
        m.inverter_enabled=False
        m.reset()
        for _ in range(1000):
            m.step()
        r=m.readings()
        self.assertAlmostEqual(r['dc_voltage'],100,delta=0.1)
        self.assertEqual(r['boost_status'],'STANDBY')
        self.assertEqual(r['source_energy'],0)
        self.assertEqual(r['dc_brake_energy'],0)
        self.assertGreater(r['battery_energy'],5)
        self.assertGreater(r['boost_loss_energy'],0)
        b=energy_budget(m,r)
        self.assertLess(abs(b['residual']),0.001)
        self.assertAlmostEqual(sum(v for _,v in b['outputs'])-b['total'],b['residual'],places=7)
        m.boost_enabled=False
        self.assertIn('Boost heat',[name for name,_ in energy_budget(m,m.readings())['outputs']])
        used=m.electrical.battery_energy
        for _ in range(10):
            m.step()
        self.assertEqual(m.electrical.battery_energy,used)
        m.reset()
        self.assertEqual(m.electrical.battery_energy,0)
        self.assertEqual(m.electrical.boost_current,0)

    def test_charging_timestep_convergence(self):
        p=Parameters(initial_flux=0,dc_initial_voltage=0,precharge_voltage=0,boost_target_voltage=100,
                     chopper_min_operating_voltage=200,
                     dc_capacitance=1000,boost_input_power_limit=20)
        results=[]
        for dt in (0.002,0.00005):
            m=DynamicLoweringModel(p)
            m.rectifier_enabled=m.chopper_active=m.boost_enabled=True
            m.inverter_enabled=False
            m.reset()
            for _ in range(round(0.15/dt)):
                m.step(dt)
            results.append(m.readings())
        self.assertAlmostEqual(results[0]['dc_voltage'],results[1]['dc_voltage'],delta=0.001)
        self.assertAlmostEqual(results[0]['battery_energy'],results[1]['battery_energy'],delta=0.001)
