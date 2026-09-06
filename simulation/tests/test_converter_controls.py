from dataclasses import replace
import math
import random
import unittest

from simulation.converter_controls import exciter,chopper
from simulation.dynamic_model import DynamicLoweringModel
from simulation.examples import small_hoist
from simulation.rectifier import bridge
from simulation.visual_state import energy_budget, describe
from simulation import dynamic_induction as electrical


class ConverterTests(unittest.TestCase):
    def model(self,**changes):
        m=DynamicLoweringModel(small_hoist(initial_shaft_rpm=1530,initial_flux=0,**changes))
        m.rectifier_enabled=m.chopper_active=m.dc_exciter=True
        m.brake_released=True
        m.reset()
        return m

    def test_chopper_threshold_response_and_saturation(self):
        p=small_hoist()
        self.assertEqual(chopper(p,500,0,True),(0,0))
        command,rate=chopper(p,580,0,True)
        self.assertEqual(command,0.5)
        self.assertEqual(rate,0.5/p.chopper_response)
        self.assertEqual(chopper(p,1000,0,True)[0],1)
        self.assertLess(chopper(p,600,0.5,False)[1],0)
        r=bridge(p,400,580,True,0.25)
        self.assertAlmostEqual(r['brake_power'],0.25*580**2/p.dc_brake_resistance)

    def test_inverter_simultaneous_limits_and_power(self):
        p=small_hoist()
        rng=random.Random(31)
        statuses=set()
        for _ in range(300):
            voltage=complex(rng.uniform(-500,500),rng.uniform(-500,500))
            request=complex(rng.uniform(-20,20),rng.uniform(-20,20))
            dc=rng.uniform(100,800)
            r=exciter(p,voltage,request,dc,True)
            statuses.add(r['status'])
            self.assertLessEqual(abs(r['current']),math.sqrt(2)*p.inverter_current_limit+1e-9)
            self.assertLessEqual(abs(r['internal_voltage']),dc/math.sqrt(3)+1e-9)
            self.assertAlmostEqual(r['dc_power'],1.5*(voltage*r['current'].conjugate()).real+r['loss'])
            self.assertGreaterEqual(r['loss'],0)
        self.assertIn('CURRENT LIMIT',statuses)
        self.assertIn('AC OVERVOLTAGE BLOCK',statuses)

    def test_zero_dc_has_no_hidden_energy_source(self):
        m=self.model(dc_initial_voltage=0)
        for _ in range(50):
            m.step()
        r=m.readings()
        self.assertEqual(r['inverter_status'],'DC TOO LOW')
        self.assertEqual(r['line_voltage'],0)
        self.assertEqual(r['inverter_current'],0)
        self.assertEqual(r['source_energy'],0)
        self.assertEqual(describe(m,r,[])['field_title'],'Waiting for starting energy')
        history=[(0,)+(0,)*13+(1.0,)]
        self.assertEqual(describe(m,r,history)['field_title'],'Excitation has collapsed')

    def test_regeneration_returns_energy_minus_loss(self):
        r=exciter(small_hoist(),200+0j,-1+0j,600,True)
        self.assertLess(r['dc_power'],0)
        self.assertAlmostEqual(r['dc_power'],-300+r['loss'])

    def test_phase_six_controls_resistor_with_ideal_external_exciter(self):
        m=self.model(dc_initial_voltage=0,chopper_threshold=500)
        m.dc_exciter=False
        for _ in range(150):
            m.step()
        r=m.readings()
        self.assertGreater(r['chopper_duty'],0.1)
        self.assertLess(r['chopper_duty'],1)
        self.assertNotEqual(r['source_energy'],0)  # Ideal boundary may supply or absorb.
        self.assertGreater(r['dc_brake_energy'],0)
        self.assertLess(abs(r['energy_residual']),0.01)

    def test_coupled_precharge_energy_and_live_controls(self):
        m=self.model(dc_initial_voltage=600)
        for _ in range(150):
            m.step()
        r=m.readings()
        self.assertGreater(r['line_voltage'],300)
        self.assertGreater(r['chopper_duty'],0)
        self.assertGreater(r['inverter_loss_energy'],0)
        self.assertEqual(r['source_energy'],0)
        saved=(m.state.time,m.electrical.dc_voltage,m.electrical.chopper_duty)
        m.parameters=replace(m.parameters,inverter_current_limit=0.3,chopper_threshold=500)
        self.assertEqual(saved,(m.state.time,m.electrical.dc_voltage,m.electrical.chopper_duty))
        self.assertLessEqual(m.readings()['inverter_current'],0.3+1e-9)
        for _ in range(50):
            m.step()
        r=m.readings()
        budget=energy_budget(m,r)
        self.assertLess(abs(budget['residual']),0.02)
        self.assertAlmostEqual(sum(v for _,v in budget['outputs'])-budget['total'],budget['residual'],places=7)
        m.inverter_enabled=False
        self.assertEqual(m.readings()['inverter_dc_power'],0)
        self.assertEqual(m.readings()['inverter_loss'],0)
        m.reset()
        self.assertEqual(m.electrical.chopper_duty,0)
        self.assertEqual(m.electrical.inverter_loss_energy,0)

    def test_chopper_disabled_duty_decays(self):
        m=self.model(dc_initial_voltage=600)
        m.inverter_enabled=False
        m.electrical.chopper_duty=0.8
        m.chopper_enabled=False
        for _ in range(20):
            m.step()
        self.assertAlmostEqual(m.electrical.chopper_duty,0.8*math.exp(-0.04/m.parameters.chopper_response),places=7)

    def test_phase_seven_timestep_convergence(self):
        saved=electrical.ELECTRICAL_DT
        results=[]
        try:
            for dt in (0.0001,0.00001):
                electrical.ELECTRICAL_DT=dt
                m=self.model(dc_initial_voltage=600)
                for _ in range(50):
                    m.step()
                r=m.readings()
                results.append((r['dc_voltage'],r['line_voltage'],r['chopper_duty']))
                self.assertLess(abs(r['energy_residual']),0.01)
        finally:
            electrical.ELECTRICAL_DT=saved
        for a,b in zip(*results):
            self.assertAlmostEqual(a,b,delta=0.001)
