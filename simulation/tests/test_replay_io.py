import csv
from dataclasses import fields, replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from simulation.external_model import ControlInputs, ExternalLoweringModel
from simulation.parameters import Parameters
from simulation.replay_io import (
    FORMAT_ID, FORMAT_VERSION, ReplayFrame, ReplayState, load_pre_simulation,
    parameter_snapshot, replay_parameters, save_pre_simulation,
    scalar_configuration)
from simulation.ui import Application


class _Variable:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Widget:
    def __init__(self):
        self.configuration = {}

    def configure(self, **values):
        self.configuration.update(values)


class ReplayPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.frames = (
            ReplayFrame(
                0.0,
                {
                    '_time': 0.0,
                    'position': 0.0,
                    'velocity': 0.25,
                    'rpm': 120.0,
                    'line_voltage': 398.5,
                    'machine_line_current': 2.75,
                    'fault': '',
                    'k_main': False,
                    'optional_value': None,
                    'power_diagnostics': {
                        'kcl': 1.25e-12,
                        'components': {'machine': {'heat': 42.0}},
                    },
                },
                ReplayState(0.0, 0.0, 0.1, 12.0, False, 0.0, 0.0),
                False, True, True, False),
            ReplayFrame(
                0.02,
                {
                    '_time': 0.02,
                    'position': 0.005,
                    'velocity': 0.30,
                    'rpm': 150.0,
                    'line_voltage': 401.0,
                    'machine_line_current': 2.9,
                    'fault': 'TEST',
                    'k_main': True,
                    'optional_value': None,
                    'power_diagnostics': {
                        'kcl': -2.5e-12,
                        'components': {'machine': {'heat': 44.0}},
                    },
                },
                ReplayState(0.02, 0.005, 0.35, 15.0, False, 0.0, 0.0),
                True, True, True, False),
        )

    def test_csv_and_json_round_trip_every_replay_value(self):
        parameters = replace(Parameters(), mass=300.0, capacitor_capacitance=6.0)
        controls = ControlInputs(automatic_profile=True, speed_request_hz=20.0)
        with tempfile.TemporaryDirectory() as directory:
            csv_path, metadata_path, metadata = save_pre_simulation(
                Path(directory) / 'lowering.csv', self.frames,
                parameter_snapshot(parameters),
                {'controller_inputs': scalar_configuration(controls)}, 0.02)
            loaded_from_csv = load_pre_simulation(csv_path)
            loaded_from_json = load_pre_simulation(metadata_path)

            self.assertEqual(loaded_from_csv.frames, self.frames)
            self.assertEqual(loaded_from_json.frames, self.frames)
            self.assertEqual(metadata['format'], FORMAT_ID)
            self.assertEqual(metadata['format_version'], FORMAT_VERSION)
            self.assertEqual(metadata['frame_count'], 2)
            self.assertTrue(csv_path.read_bytes().startswith(b'\xef\xbb\xbf'))

            with csv_path.open(encoding='utf-8-sig', newline='') as stream:
                columns = next(csv.reader(stream))
            self.assertIn('time_s', columns)
            self.assertIn('load_speed_m_min', columns)
            self.assertIn('motor_rpm', columns)
            self.assertIn('ac_voltage_v_ll_rms', columns)
            self.assertIn('motor_current_a_rms', columns)

    def test_parameter_snapshot_automatically_contains_every_field_and_unit(self):
        parameters = Parameters()
        snapshot = parameter_snapshot(parameters)
        self.assertEqual(set(snapshot), {item.name for item in fields(parameters)})
        for item in fields(parameters):
            self.assertEqual(snapshot[item.name]['value'], getattr(parameters, item.name))
            self.assertEqual(snapshot[item.name]['unit'], item.metadata['unit'])
        self.assertEqual(snapshot['mass']['unit'], 'kg')
        self.assertEqual(snapshot['exciter_flux_target']['unit'], 'Wb turn')

    def test_complete_real_model_telemetry_and_configuration_round_trip(self):
        model = ExternalLoweringModel()
        readings = model.readings()
        readings['_time'] = model.state.time
        frame = ReplayFrame(
            model.state.time, readings,
            ReplayState(model.state.time, model.state.position, model.state.angle,
                        model.state.omega, model.state.grounded,
                        model.state.impact_speed, model.state.impact_energy),
            model.brake_released, model.motor_connected,
            model.inverter_enabled, model.capacitors_enabled)
        with tempfile.TemporaryDirectory() as directory:
            csv_path, _, metadata = save_pre_simulation(
                Path(directory) / 'real-model.csv', (frame,),
                parameter_snapshot(model.parameters),
                {'model_configuration': scalar_configuration(model)}, 0.02)
            loaded = load_pre_simulation(csv_path)
        self.assertEqual(loaded.frames[0], frame)
        configuration = metadata['run_configuration']['model_configuration']
        self.assertEqual(configuration['excitation_mode'], 'exciter')
        self.assertIn('controls', configuration)
        self.assertIn('electrical', configuration)

    def test_saved_parameters_make_separate_display_context(self):
        current = Parameters(mass=100.0)
        saved = parameter_snapshot(replace(current, mass=300.0))
        context = replay_parameters(saved, current)
        self.assertEqual(context.mass, 300.0)
        self.assertEqual(current.mass, 100.0)
        self.assertIsNot(context, current)

    def test_ui_load_reconstructs_player_without_resetting_or_stepping_model(self):
        current_parameters = Parameters(mass=100.0)
        saved_parameters = replace(current_parameters, mass=300.0)
        with tempfile.TemporaryDirectory() as directory:
            csv_path, _, _ = save_pre_simulation(
                Path(directory) / 'ui-load.csv', self.frames,
                parameter_snapshot(saved_parameters), {}, 0.02)

            class UntouchedModel:
                parameters = current_parameters
                kernel = SimpleNamespace(cac=0.123)
                state = self.frames[0].state

                def reset(self):
                    raise AssertionError('load must not reset physics')

                def step(self, _duration):
                    raise AssertionError('load must not step physics')

            app = Application.__new__(Application)
            app.model = UntouchedModel()
            app.message = _Variable()
            app.playing = True
            app.play_button = _Widget()
            app.presim_running = True
            app.presim_frames = []
            app.presim_index = 0
            app.presim_wall = 0.0
            app.active_speed = 1.0
            app.replay_history = []
            app.presim_seconds = _Variable()
            app.presim_progress = _Variable()
            app.presim_save_button = _Widget()
            app.presim_view_button = _Widget()
            app.replay_context_message = _Variable()
            app.energy_view = SimpleNamespace(refresh=lambda: None)
            app.presim_parameter_snapshot = None
            app.presim_run_configuration = None
            app.replay_parameters = None
            app.replay_model_context = None
            app.loaded_replay_source = None

            with patch('simulation.ui.filedialog.askopenfilename',
                       return_value=str(csv_path)):
                Application.load_pre_simulation(app)

        self.assertIs(app.model.parameters, current_parameters)
        self.assertEqual(app.replay_parameters.mass, 300.0)
        self.assertEqual(app.presim_frames, list(self.frames))
        self.assertFalse(app.playing)
        self.assertIn('without running physics', app.message.get())
        state, readings, _, flags = Application.display_snapshot(app)
        self.assertEqual(state, self.frames[0].state)
        self.assertEqual(readings, self.frames[0].readings)
        self.assertTrue(flags['motor_connected'])

    def test_version_and_checksum_are_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path, metadata_path, _ = save_pre_simulation(
                Path(directory) / 'run.csv', self.frames,
                parameter_snapshot(Parameters()), {}, 0.02)
            data = json.loads(metadata_path.read_text(encoding='utf-8'))
            data['format_version'] = FORMAT_VERSION + 1
            metadata_path.write_text(json.dumps(data), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unsupported replay format'):
                load_pre_simulation(csv_path)

            data['format_version'] = FORMAT_VERSION
            metadata_path.write_text(json.dumps(data), encoding='utf-8')
            with csv_path.open('a', encoding='utf-8') as stream:
                stream.write('\n')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                load_pre_simulation(metadata_path)


if __name__ == '__main__':
    unittest.main()
