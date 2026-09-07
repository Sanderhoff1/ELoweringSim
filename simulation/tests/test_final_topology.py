import unittest

from simulation.external_model import ExternalLoweringModel, reviewed_parameters


def advance(model, seconds=.05):
    for _ in range(round(seconds/.001)):
        model.step(.001)
    return model.readings()


class FinalTopologyTests(unittest.TestCase):
    def test_exciter_mode_has_no_capacitor_state_or_current(self):
        m=ExternalLoweringModel(reviewed_parameters(capacitor_capacitance=0))
        m.excitation_mode='exciter'; m.start_mode='external_supply'; m.reset()
        r=advance(m)
        self.assertEqual(r['capacitor_energy'],0)
        self.assertEqual(r['capacitor_line_current'],0)
        self.assertGreaterEqual(r['battery_soc'],0)

    def test_capacitor_mode_disconnects_exciter(self):
        m=ExternalLoweringModel(reviewed_parameters(initial_flux=.02))
        m.excitation_mode='capacitor'; m.start_mode='residual'; m.reset()
        r=advance(m)
        self.assertEqual(r['inverter_real_power'],0)
        self.assertEqual(r['capacitor_energy'] >= 0, True)

    def test_precharge_draws_finite_battery_energy(self):
        p=reviewed_parameters(precharge_voltage=100)
        m=ExternalLoweringModel(p); m.excitation_mode='capacitor'; m.start_mode='precharged'; m.reset()
        self.assertLess(m.electrical.battery_energy,p.battery_capacity_wh*3600)
        self.assertGreater(m.electrical.precharge_loss_energy,0)

    def test_charger_is_bounded_by_soc(self):
        m=ExternalLoweringModel(); m.electrical.battery_energy=m.parameters.battery_capacity_wh*3600
        r=advance(m)
        self.assertLessEqual(r['battery_soc'],100)

