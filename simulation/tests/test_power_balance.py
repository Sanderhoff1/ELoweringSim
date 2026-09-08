import math
import unittest
from simulation.external_model import ExternalLoweringModel, Kernel, reviewed_parameters
from simulation.auxiliary import battery, boost_limit, discharge_limit, paths


class PowerBalanceTests(unittest.TestCase):
    def check_balance(self,m):
        r=m.readings()
        d=r['power_diagnostics']
        self.assertLess(abs(d['kcl']),2e-8)
        self.assertLess(abs(d['reactive_residual']),2e-5)
        port=d['connections']['exciter_bus']
        if port['current']>1e-6:
            internal_squared=(2/3*port['voltage']**2+2*m.parameters.inverter_output_resistance**2*port['current']**2
                              +4/3*m.parameters.inverter_output_resistance*port['power'])
            self.assertLessEqual(internal_squared,m.parameters.boost_target_voltage**2/3+1e-4)

        for name,c in d['components'].items():
            self.assertLess(abs(c['residual']),2e-5,name)
        self.assertLess(abs(r['battery_current']),max(m.parameters.battery_charge_current_limit,m.parameters.battery_discharge_current_limit)+1e-8)
        self.assertAlmostEqual(r['battery_loss'],r['battery_current']**2*m.parameters.battery_internal_resistance,places=9)
        return r

    def test_startup_transient_and_steady_exciter(self):
        m=ExternalLoweringModel()
        self.check_balance(m)
        for target in (.05,.5,1.,3.):
            while m.state.time<target-1e-9:m.step()
            r=self.check_balance(m)
            self.assertLess(abs(r['energy_residual']),.002)
        self.assertTrue(.24<r['velocity']<.31)
        self.assertLess(abs(r['acceleration']),.01)
        self.assertEqual(r['external_supply_power'],0)

    def test_capacitor_only_and_precharge_at_zero(self):
        m=ExternalLoweringModel(reviewed_parameters(precharge_voltage=200,initial_shaft_rpm=1600))
        m.excitation_mode='capacitor';m.start_mode='precharged';m.startup_enabled=False;m.brake_released=True;m.reset()
        r=self.check_balance(m)
        self.assertLess(abs(r['energy_residual']),1e-9)
        initial_battery=m.parameters.battery_capacity_wh*3600
        self.assertAlmostEqual(initial_battery-m.electrical.battery_energy,r['capacitor_energy']+m.electrical.precharge_loss_energy,places=8)
        for target in (.01,.1,.5,3.):
            while m.state.time<target-1e-9:m.step()
            r=self.check_balance(m)
            self.assertLess(abs(r['energy_residual']),.01)

    def test_magnetic_storage_is_derivative_of_energy(self):
        p=reviewed_parameters();k=Kernel(p)
        ps,pr,v=.9+.2j,.7-.1j,160+80j
        a=k.rate((ps,pr,v),0,50,160,500,False,True,True)
        eps=1e-7
        derivative=(k.stored(ps+eps*a.ps,pr+eps*a.pr,v)[0]-k.stored(ps-eps*a.ps,pr-eps*a.pr,v)[0])/(2*eps)
        self.assertAlmostEqual(derivative,1.5*(v*a.winding_current.conjugate()).real-a.copper-a.torque*160,delta=2e-5)

    def test_current_and_power_limit_never_hide_ac_power(self):
        for changes in (dict(inverter_current_limit=.1),dict(boost_input_power_limit=5),dict(battery_discharge_current_limit=.01),dict(boost_output_current_limit=.01)):
            m=ExternalLoweringModel(reviewed_parameters(**changes))
            for _ in range(50):m.step()
            r=self.check_balance(m)
            self.assertLessEqual(r['inverter_current'],m.parameters.inverter_current_limit+1e-8)
            self.assertLessEqual(r['boost_power'],boost_limit(m.parameters)+1e-7)
            self.assertLessEqual(r['battery_current'],m.parameters.battery_discharge_current_limit+1e-8)
            self.assertLess(abs(r['energy_residual']),.002)
            self.assertIsNone(m.release_time)

    def test_absorbing_power_limit_respects_voltage_capability(self):
        from simulation.external_exciter import current
        p=reviewed_parameters()
        ceiling=p.boost_target_voltage/math.sqrt(3)
        voltage=complex(ceiling+.03)
        i,supply,heat,limited=current(p,voltage,-1+3j,1j,700,True,4.)
        self.assertTrue(limited)
        self.assertEqual(i,0j)  # Blocking is required at this infeasible point.
        self.assertLessEqual(supply,4.)
        self.assertAlmostEqual(supply,1.5*(voltage*i.conjugate()).real+heat)

    def test_charge_discharge_limits_and_storage(self):
        p=reviewed_parameters(battery_charge_current_limit=.1,battery_discharge_current_limit=.2)
        for power in (-2.,0.,discharge_limit(p)):
            v,i,heat=battery(p,power)
            self.assertAlmostEqual(v*i+heat,p.battery_voltage*i,places=10)
            self.assertAlmostEqual(v,p.battery_voltage-p.battery_internal_resistance*i)
        a=paths(p,100,0,500,.001)
        self.assertAlmostEqual(a['current'],-.1)
        self.assertAlmostEqual(a['charger_input'],a['charger_output']+a['charger_heat'])
        a=paths(p,100,boost_limit(p),0,.001)
        self.assertLessEqual(a['current'],.2+1e-12)
        self.assertAlmostEqual(a['boost_input'],a['boost_output']+a['boost_heat'])


if __name__=='__main__':unittest.main()
