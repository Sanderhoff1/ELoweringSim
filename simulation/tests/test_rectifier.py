from dataclasses import replace
import math
import unittest

from simulation.parameters import Parameters
from simulation.dynamic_model import DynamicLoweringModel
from simulation import dynamic_induction as electrical
from simulation.rectifier import bridge, K
from simulation.visual_state import energy_budget, describe


class RectifierTests(unittest.TestCase):
    def test_forward_power_balance_and_reverse_block(self):
        p = Parameters()
        for voltage, dc in [(300+100j,100), (0j,500), (100j,500)]:
            r = bridge(p,voltage,dc,True)
            self.assertGreaterEqual(r['current'],0)
            self.assertAlmostEqual(1.5*(voltage*r['ac_current'].conjugate()).real,r['power'])
            self.assertAlmostEqual(r['power'],r['dc_power']+r['loss'])
        self.assertEqual(bridge(p,100j,500,True)['current'],0)

    def test_dc_discharge_is_analytic_and_cannot_backfeed(self):
        p = Parameters(initial_flux=0,precharge_voltage=0,dc_initial_voltage=500)
        m = DynamicLoweringModel(p)
        m.rectifier_enabled=True
        m.inverter_enabled=False
        m.reset()
        for _ in range(100):
            m.step()
        r = m.readings()
        expected = 500*math.exp(-0.2/(p.dc_brake_resistance*p.dc_capacitance*1e-6))
        self.assertAlmostEqual(r['dc_voltage'],expected,places=7)
        self.assertEqual(r['line_voltage'],0)
        self.assertEqual(r['rectifier_power'],0)
        self.assertLess(abs(r['energy_residual']),1e-7)

    def test_energized_bus_and_live_resistance_conserve_energy(self):
        p = Parameters(precharge_voltage=40,initial_shaft_rpm=240)
        m = DynamicLoweringModel(p)
        m.rectifier_enabled=True
        m.brake_released=True
        m.reset()
        for _ in range(150):
            m.step()
        r=m.readings()
        emf=K*math.sqrt(2/3)*40
        self.assertAlmostEqual(r['dc_voltage'],emf*p.dc_brake_resistance/(p.rectifier_resistance+p.dc_brake_resistance),delta=0.2)
        self.assertEqual(r['load_power'],0)
        self.assertGreater(r['dc_brake_energy'],0)
        before=m.electrical.dc_voltage
        m.parameters=replace(p,dc_brake_resistance=100)
        self.assertEqual(m.electrical.dc_voltage,before)
        for _ in range(100):
            m.step()
        budget=energy_budget(m,m.readings())
        self.assertLess(abs(budget['residual']),0.01)
        self.assertAlmostEqual(sum(v for _,v in budget['outputs'])-budget['total'],budget['residual'],places=8)

    def test_no_ac_capacitors_and_no_exciter(self):
        m=DynamicLoweringModel(Parameters(initial_flux=0.005,dc_initial_voltage=20))
        m.rectifier_enabled=True
        m.capacitors_enabled=False
        m.inverter_enabled=False
        m.reset()
        with self.assertRaisesRegex(ValueError,'nonzero AC capacitor'):
            m.step()

    def test_voltage_bar_is_linear_and_independent_of_frequency_command(self):
        m=DynamicLoweringModel(Parameters(precharge_voltage=200,supply_frequency=5,motor_rated_voltage=400))
        view=describe(m,m.readings(),[])
        self.assertAlmostEqual(view['voltage_ratio'],0.5)

    def test_dc_timestep_convergence(self):
        p=Parameters(initial_flux=0,precharge_voltage=40)
        results=[]
        for dt in (0.0001,0.00005):
            state=electrical.initial_state(p)
            for _ in range(round(0.1/dt)):
                electrical.advance(p,state,dt,0,True,True,True,True)
            results.append(state.dc_voltage)
        self.assertAlmostEqual(*results,places=6)
