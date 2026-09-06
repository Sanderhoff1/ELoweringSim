import unittest

from simulation.dynamic_model import DynamicLoweringModel
from simulation.visual_state import describe


class VisualStateTests(unittest.TestCase):
    def setUp(self):
        self.model = DynamicLoweringModel()
        self.model.motor_connected = True
        self.r = self.model.readings()

    def test_generating_does_not_mean_slowing(self):
        self.r.update(velocity=2, acceleration=1, omega=20,
                      motor_torque=-10, motor_shaft_power=-200)
        view = describe(self.model, self.r, [])
        self.assertEqual(view['motion'], 'Load is speeding up')
        self.assertEqual(view['torque_text'], 'Machine opposes the motion')
        self.assertEqual(view['shaft_power'], 200)

    def test_capacitor_charging_and_discharge_balance(self):
        self.r.update(inverter_real_power=100, electrical_export=40, load_power=30)
        self.assertEqual(describe(self.model, self.r, [])['cap_absorption'], 110)
        self.r.update(inverter_real_power=0, electrical_export=-40)
        self.assertEqual(describe(self.model, self.r, [])['cap_absorption'], -70)

    def test_field_fades_without_being_immediately_erased(self):
        self.model.inverter_enabled = False
        self.model.state.time = 1
        self.r['flux_magnitude'] = 0.2
        history = [(0.5,) + (0,) * 13 + (0.5,)]
        view = describe(self.model, self.r, history)
        self.assertEqual(view['field_title'], 'Magnetic field is fading')
        self.assertGreater(view['field_ratio'], 0)

    def test_zero_field_and_grounded_load(self):
        self.r['flux_magnitude'] = 0
        self.model.state.grounded = True
        view = describe(self.model, self.r, [])
        self.assertEqual(view['field_title'], 'No magnetic field yet')
        self.assertEqual(view['motion'], 'Load has reached the ground')
