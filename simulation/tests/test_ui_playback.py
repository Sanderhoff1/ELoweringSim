import math
import unittest

from simulation.ui import (DISCRETE_TELEMETRY, ReplayFrame, ReplayState,
                           interpolate_telemetry)


class PlaybackTelemetryTests(unittest.TestCase):
    def test_continuous_values_and_nested_diagnostics_interpolate(self):
        before={'position':2.0,'power_diagnostics':{'kcl':-2.0}}
        after={'position':6.0,'power_diagnostics':{'kcl':2.0}}
        value=interpolate_telemetry(before,after,.25)
        self.assertEqual(value['position'],3.0)
        self.assertEqual(value['power_diagnostics']['kcl'],-1.0)

    def test_switches_and_faults_are_not_interpolated(self):
        before={'k_main':False,'fault':'NONE','main_dc_connection':'PRECHARGE'}
        after={'k_main':True,'fault':'TRIP','main_dc_connection':'MAIN'}
        value=interpolate_telemetry(before,after,.75)
        self.assertEqual(value,before)
        self.assertTrue(set(before).issubset(DISCRETE_TELEMETRY))

    def test_flux_angle_uses_short_wrapped_path(self):
        value=interpolate_telemetry({'flux_angle':math.radians(350)},
                                    {'flux_angle':math.radians(10)},.5)
        self.assertAlmostEqual(value['flux_angle'] % (2*math.pi),0.0,places=12)

    def test_replay_frame_contains_data_not_a_model_copy(self):
        frame=ReplayFrame(0.0,{'position':0.0},
                          ReplayState(0,0,0,0,False,0,0),
                          False,True,True,False)
        self.assertFalse(hasattr(frame,'model'))
        self.assertEqual(frame.readings['position'],0.0)


if __name__ == '__main__':
    unittest.main()
