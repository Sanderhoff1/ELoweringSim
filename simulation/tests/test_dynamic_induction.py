from dataclasses import replace
import math
import unittest

from simulation.parameters import Parameters
from simulation import dynamic_induction as electrical
from simulation.dynamic_model import DynamicLoweringModel
from simulation.mechanical import Playback


def evolve(p, omega, seconds, inverter=False, state=None, dt=0.0001):
    state = state or electrical.initial_state(p)
    for _ in range(round(seconds/dt)):
        electrical.advance(p, state, dt, omega, inverter, True)
    return state, electrical.readings(p, state, omega, inverter, True)


class DynamicInductionTests(unittest.TestCase):
    def test_flux_current_inversion_and_saturation(self):
        p = Parameters()
        for ps, pr in [(0j,0j), (0.2+0.4j,0.3+0.2j), (2+3j,3+4j)]:
            is_, ir, pm = electrical.currents(p,ps,pr)
            self.assertAlmostEqual(abs(ps-p.stator_leakage*is_-pm),0,places=12)
            self.assertAlmostEqual(abs(pr-p.rotor_leakage*ir-pm),0,places=12)
            self.assertAlmostEqual(abs(is_+ir-pm/p.magnetizing_inductance*(1+abs(pm)**2/p.saturation_flux**2)),0,places=10)

    def test_zero_seed_stays_zero_at_high_speed(self):
        p = Parameters(initial_flux=0,precharge_voltage=0)
        state, r = evolve(p,50,0.5)
        self.assertEqual(state.voltage,0j)
        self.assertEqual(r['motor_torque'],0)
        self.assertEqual(r['inverter_current'],0)

    def test_precharge_decays_without_shaft_energy(self):
        p = Parameters(initial_flux=0,precharge_voltage=20)
        state = electrical.initial_state(p)
        initial_energy = sum(electrical.stored_energy(p,(state.stator_flux,state.rotor_flux,state.voltage)))
        state, r = evolve(p,0,1,state=state)
        self.assertLess(r['line_voltage'],0.02)
        self.assertAlmostEqual(r['magnetic_energy']+r['capacitor_energy']+state.load_energy+state.copper_energy,
                               initial_energy,places=7)

    def test_seed_builds_and_saturation_limits_voltage(self):
        p = Parameters()
        state, at8 = evolve(p,25,8)
        state, at10 = evolve(p,25,2,state=state)
        self.assertGreater(at10['line_voltage'],40)
        self.assertLess(at10['line_voltage'],60)
        self.assertLess(abs(at10['line_voltage']-at8['line_voltage']),0.1)
        self.assertLess(at10['motor_torque'],0)
        self.assertEqual(state.source_energy,0)

    def test_insufficient_speed_decays(self):
        _, r = evolve(Parameters(precharge_voltage=20),5,1)
        self.assertLess(r['line_voltage'],1)

    def test_switch_off_preserves_states_and_can_sustain(self):
        p = Parameters(initial_flux=0)
        state, before = evolve(p,25,1,inverter=True)
        saved = (state.stator_flux,state.rotor_flux,state.voltage)
        after = electrical.readings(p,state,25,False,True)
        self.assertEqual(saved,(state.stator_flux,state.rotor_flux,state.voltage))
        self.assertEqual(before['line_voltage'],after['line_voltage'])
        self.assertEqual(after['inverter_current'],0)
        source_energy = state.source_energy
        state, after = evolve(p,25,3,state=state)
        self.assertGreater(after['line_voltage'],40)
        self.assertEqual(state.source_energy,source_energy)

    def test_circuit_instantaneous_energy_balance(self):
        p = Parameters()
        y = (0.3+0.1j, 0.2+0.15j, 10+20j)
        derivative, r = electrical.circuit(p,y,0.123,25,False,True)
        h = 1e-7
        plus = tuple(v+h*d for v,d in zip(y,derivative))
        minus = tuple(v-h*d for v,d in zip(y,derivative))
        energy_rate = (sum(electrical.stored_energy(p,plus))-sum(electrical.stored_energy(p,minus)))/(2*h)
        expected = r['source_power']-r['load_power']-r['copper_power']-r['torque']*25
        self.assertAlmostEqual(energy_rate,expected,places=5)

    def test_coupled_energy_and_timestep_refinement(self):
        p = Parameters(initial_shaft_rpm=240,inertia=20,crane_height=100,precharge_voltage=20)
        outputs = []
        old_dt = electrical.ELECTRICAL_DT
        try:
            for dt in (0.0001,0.00005):
                electrical.ELECTRICAL_DT = dt
                m = DynamicLoweringModel(p)
                m.inverter_enabled=False
                m.brake_released=True
                for _ in range(500):
                    m.step()
                r=m.readings()
                self.assertLess(abs(r['energy_residual']),0.001)
                outputs.append((m.state.omega,r['line_voltage']))
        finally:
            electrical.ELECTRICAL_DT = old_dt
        for a,b in zip(*outputs):
            self.assertAlmostEqual(a,b,places=4)

    def test_playback_reset_and_ground(self):
        p=Parameters(initial_shaft_rpm=240,precharge_voltage=20,crane_height=0.1)
        states=[]
        for speed,frames in [(0.1,60),(1,6),(10,1)]:
            m=DynamicLoweringModel(p)
            m.inverter_enabled=False
            m.brake_released=True
            clock=Playback(m)
            for _ in range(frames):
                clock.advance(0.1/speed/frames,speed)
            self.assertTrue(m.state.grounded)
            self.assertEqual(m.state.position,0.1)
            states.append((m.state,m.electrical))
        self.assertEqual(states[0],states[1])
        self.assertEqual(states[0],states[2])
        m.reset()
        self.assertAlmostEqual(m.readings()['line_voltage'],20)
        self.assertEqual(m.electrical.source_energy,0)
        self.assertFalse(m.state.grounded)

    def test_no_capacitor_bus_and_open_machine(self):
        p=Parameters(initial_flux=0)
        state=electrical.initial_state(p)
        _,r=electrical.circuit(p,(state.stator_flux,state.rotor_flux,state.voltage),0.1,25,False,False)
        self.assertEqual(r['voltage'],0)
        _,r=electrical.circuit(p,(0.01+0j,0.01+0j,20+0j),0.1,25,False,True,False)
        self.assertEqual(r['stator_current'],0)
        self.assertEqual(r['torque'],0)
