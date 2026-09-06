import math
import unittest
from dataclasses import replace
from simulation.external_model import ExternalLoweringModel, Kernel, reviewed_parameters
from simulation.external_exciter import current
from simulation.capacitor_rectifier import transfer, midpoint_voltage
from simulation.equivalent_circuit import operating_point
from simulation.mechanical import MechanicalModel
from simulation.visual_state import energy_budget
from simulation.validation import dynamic_operating_point, CASES


def run(model,seconds,dt=.002):
    for _ in range(round(seconds/dt)):
        model.step(dt)
    return model.readings()


class BridgeTests(unittest.TestCase):
    def test_capacitor_input_threshold_and_quadrature(self):
        peak=math.sqrt(2)*400
        self.assertEqual(transfer(400,peak,12),(0,0,0))
        self.assertGreater(transfer(400,550,12)[0],0)  # Above 1.35*400.
        for voltage in (0,300,490,550,peak-1e-3,600):
            with self.subTest(voltage=voltage):
                i,p,loss=transfer(400,voltage,12)
                self.assertAlmostEqual(p,voltage*i+loss,places=9)
                n=20000
                samples=[peak*math.cos(-math.pi/6+(j+.5)*math.pi/(3*n)) for j in range(n)]
                expected_i=sum(max(0,(v-voltage)/12) for v in samples)/n
                expected_p=sum(v*max(0,(v-voltage)/12) for v in samples)/n
                self.assertAlmostEqual(i,expected_i,delta=1e-7)
                self.assertAlmostEqual(p,expected_p,delta=1e-4)

    def test_positive_midpoint_discharge_conserves_energy(self):
        c=.00047
        for initial_voltage in (0,1e-8,.01,1,600):
            energy=.5*c*initial_voltage**2
            initial=energy
            heat=0
            for _ in range(100):
                h=.0002
                v=midpoint_voltage(energy,c,h,0,12,1/50)
                loss=h*v*v/50
                energy-=loss
                heat+=loss
                self.assertGreaterEqual(energy,0)
            self.assertAlmostEqual(initial,energy+heat,places=10)


class EquivalentCircuitTests(unittest.TestCase):
    def test_dynamic_machine_against_independent_t_circuit(self):
        p=reviewed_parameters()
        for slip,voltage in CASES:
            with self.subTest(slip=slip,voltage=voltage):
                expected=operating_point(p,slip,voltage)
                measured=dynamic_operating_point(p,slip,voltage)
                for key,value in measured.items():
                    self.assertAlmostEqual(value,expected[key],delta=max(.002,.0002*abs(expected[key])),msg=key)


class ReviewedSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=ExternalLoweringModel()
        cls.r=run(cls.model,3)

    def test_startup_rest_to_steady_passive_generation(self):
        m,r=self.model,self.r
        self.assertEqual(m.parameters.initial_shaft_rpm,0)
        self.assertEqual(m.parameters.dc_initial_voltage,0)
        self.assertEqual(m.parameters.precharge_voltage,0)
        self.assertEqual(m.initial_energy,0)
        self.assertGreater(m.release_time,m.parameters.startup_dwell)
        self.assertEqual(r['startup_status'],'GENERATING')
        self.assertTrue(m.brake_released)
        self.assertTrue(.24<r['velocity']<.31)
        self.assertLess(abs(r['acceleration']),.001)
        self.assertGreater(r['inverter_reactive_supply'],50)
        self.assertGreater(r['rectifier_power'],.95*r['electrical_export'])
        self.assertLess(abs(r['inverter_real_power']),.02*r['electrical_export'])
        self.assertGreater(r['dc_brake_power'],400)
        self.assertGreater(r['external_supply_power'],0)

    def test_whole_system_and_internal_energy_balances(self):
        m,r=self.model,self.r
        self.assertLess(abs(r['energy_residual']),.002)
        self.assertAlmostEqual(r['dc_energy'],r['dc_input_energy']-r['dc_brake_energy'],places=8)
        self.assertAlmostEqual(r['rectifier_energy'],r['dc_input_energy']+r['rectifier_loss_energy'],places=8)
        b=energy_budget(m,r)
        self.assertAlmostEqual(sum(v for _,v in b['outputs'])-b['total'],r['energy_residual'],places=7)
        for key in ('core_energy','gear_energy','drivetrain_energy','brake_energy','friction_energy','inverter_loss_energy'):
            self.assertGreater(r[key],0,key)

    def test_no_supply_no_seed_keeps_brake_held(self):
        m=ExternalLoweringModel()
        m.inverter_enabled=False
        r=run(m,.5)
        self.assertEqual(r['velocity'],0)
        self.assertEqual(r['dc_energy'],0)
        self.assertEqual(r['flux_magnitude'],0)
        self.assertIsNone(m.release_time)
        self.assertEqual(r['source_energy'],0)

    def test_low_dc_and_depletion(self):
        for voltage in (0,1e-6,.1,9.9,10.1):
            with self.subTest(voltage=voltage):
                m=ExternalLoweringModel(reviewed_parameters(dc_initial_voltage=voltage))
                m.inverter_enabled=False
                m.electrical.chopper_duty=1
                r=run(m,.05)
                self.assertGreaterEqual(r['dc_voltage'],0)
                self.assertGreaterEqual(r['dc_energy'],0)
                self.assertLessEqual(r['dc_voltage'],voltage)
                self.assertLess(abs(r['energy_residual']),1e-9)

    def test_timestep_convergence(self):
        results=[]
        for h in (4e-5,2e-5,1e-5):
            m=ExternalLoweringModel()
            m.max_electrical_step=h
            results.append(run(m,1.2))
        for key,tolerance in (('velocity',.001),('dc_voltage',.5),('flux_magnitude',.003)):
            self.assertLess(abs(results[0][key]-results[2][key]),tolerance,key)
            self.assertLessEqual(abs(results[1][key]-results[2][key]),abs(results[0][key]-results[2][key])+1e-8,key)
        self.assertLess(abs(results[-1]['energy_residual']),abs(results[0]['energy_residual'])+1e-6)

    def test_different_loads_use_passive_path(self):
        for mass in (200,400):
            m=ExternalLoweringModel(reviewed_parameters(mass=mass))
            r=run(m,2)
            self.assertGreater(r['rectifier_power'],.94*r['electrical_export'])
            self.assertGreater(r['dc_brake_power'],100)
            self.assertLess(abs(r['energy_residual']),.01)

    def test_core_branch_changes_electrical_demand(self):
        p=reviewed_parameters()
        low=Kernel(p)
        high=Kernel(replace(p,core_loss_resistance=1e12))
        y=(.8+.1j,.8j,200+30j)
        a=low.rate(y,0,50,160,500,False)
        b=high.rate(y,0,50,160,500,False)
        self.assertGreater(a.core,b.core)
        self.assertLess((y[2].conjugate()*(a.voltage-b.voltage)).real,0)

    def test_landing_splits_electrical_work_and_accounts_for_impact(self):
        m=ExternalLoweringModel(reviewed_parameters(crane_height=.1))
        r=run(m,2)
        self.assertTrue(m.state.grounded)
        self.assertEqual(m.state.position,.1)
        self.assertEqual(r['velocity'],0)
        self.assertGreater(m.state.impact_energy,100)
        self.assertLess(abs(r['energy_residual']),.002)

    def test_mechanical_losses_are_configurable(self):
        p=reviewed_parameters(brake_torque=0,damping=0)
        m=MechanicalModel(p)
        m.step(.1)
        expected=(p.mass*p.gravity*p.radius*p.gearbox_efficiency-p.drivetrain_loss_torque)/ (p.inertia+p.mass*p.radius**2)
        self.assertAlmostEqual(m.state.omega,expected*.1)

    def test_exciter_cannot_regenerate_through_external_supply(self):
        p=reviewed_parameters()
        for voltage in (0,1,200,325,500):
            for demand in (-100+100j,100+100j,0j):
                ie,supply,loss,_=current(p,complex(voltage),demand,1j,700,True)
                pac=1.5*voltage*ie.real
                self.assertGreaterEqual(supply,0)
                self.assertGreaterEqual(pac,-p.exciter_absorption_limit-1e-9)
                self.assertLessEqual(pac,p.exciter_active_limit+1e-9)
                self.assertLessEqual(abs(ie),math.sqrt(2)*p.inverter_current_limit+1e-9)
                self.assertAlmostEqual(supply,pac+loss,places=8)


if __name__=='__main__':
    unittest.main()
