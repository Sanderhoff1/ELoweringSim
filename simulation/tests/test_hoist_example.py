import math
import unittest

from simulation.examples import small_hoist
from simulation.dynamic_model import DynamicLoweringModel
from simulation.visual_state import energy_budget
from simulation.tests.test_dynamic_induction import evolve


class HoistExampleTests(unittest.TestCase):
    def test_estimated_rated_point(self):
        p = small_hoist()
        _, r = evolve(p,1420*2*math.pi/60,1,inverter=True)
        self.assertAlmostEqual(r['motor_shaft_power'],900,delta=45)
        self.assertEqual(p.pole_pairs,2)
        self.assertAlmostEqual(p.mass*p.gravity*p.crane_height,588600)
        self.assertLess(p.mass*p.gravity*p.radius,900/(1420*2*math.pi/60))

    def test_inventory_closes_with_exciter_and_initial_charge(self):
        model = DynamicLoweringModel(small_hoist(initial_shaft_rpm=1530,precharge_voltage=200))
        model.brake_released = True
        model.reset()
        for enabled in (True,False):
            model.inverter_enabled = enabled
            for _ in range(150):
                model.step()
            r = model.readings()
            budget = energy_budget(model,r)
            self.assertAlmostEqual(sum(v for _,v in budget['outputs'])-budget['total'],
                                   budget['residual'],places=7)
            self.assertLess(abs(budget['residual']),0.1)
        model.reset()
        self.assertEqual(model.mechanical_dissipation,0)
        self.assertEqual(model.readings()['source_energy'],0)

    def test_ground_impact_is_in_inventory(self):
        model = DynamicLoweringModel(small_hoist(crane_height=0.01,initial_shaft_rpm=1530,initial_flux=0))
        model.inverter_enabled = False
        model.brake_released = True
        model.reset()
        for _ in range(40):
            model.step()
        self.assertTrue(model.state.grounded)
        budget = energy_budget(model,model.readings())
        self.assertAlmostEqual(budget['outputs'][0][1],0)
        self.assertGreater(model.mechanical_dissipation,model.state.impact_energy*0.99)
        self.assertLess(abs(budget['residual']),0.1)
