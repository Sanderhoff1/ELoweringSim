"""Canonical automatic backup-lowering simulations and reports."""
from csv import DictWriter
from pathlib import Path
import json
import sys

from .external_model import ExternalLoweringModel, reviewed_parameters


FIELDS = (
    'time', 'sequence_state', 'stator_frequency_command', 'frequency_target',
    'velocity', 'acceleration', 'rpm', 'synchronous_rpm', 'slip', 'line_voltage', 'bus_frequency',
    'machine_line_current', 'machine_active_current', 'machine_reactive_current',
    'machine_current_limit',
    'capacitor_line_current', 'capacitor_reactive_supply',
    'flux_magnitude', 'flux_target', 'maximum_flux', 'voltage_command',
    'vf_base_voltage', 'vf_resistive_compensation', 'vf_flux_correction',
    'vf_unlimited_voltage', 'vf_flux_error', 'vf_flux_integral',
    'excitation_scale', 'motor_torque', 'motor_shaft_power',
    'machine_copper_loss', 'machine_core_loss', 'magnetic_storage_power',
    'electrical_export', 'machine_reactive_demand', 'rectifier_current',
    'rectifier_power', 'dc_input_power', 'dc_voltage', 'dc_capacitor_current',
    'dc_capacitor_power', 'chopper_duty', 'dc_brake_power', 'brake_command',
    'brake_physical_state', 'brake_capacity', 'k_exc', 'k_precharge', 'k_main',
    'aux_voltage', 'aux_power', 'boost_power', 'battery_voltage',
    'battery_current', 'battery_power', 'inverter_real_power','inverter_reactive_supply',
    'vf_current_limited', 'vf_flux_limited','vf_voltage_limited',
    'power_transfer_limited', 'runaway', 'fault', 'energy_residual')


def run(mode='exciter', seconds=None, sample_steps=5, changes=None):
    seconds = 11.0 if mode == 'exciter' and seconds is None else 8.0 if seconds is None else seconds
    parameter_changes = {} if mode == 'exciter' else {'initial_flux': .005}
    parameter_changes.update(changes or {})
    model = ExternalLoweringModel(reviewed_parameters(**parameter_changes))
    model.excitation_mode = mode
    model.start_mode = 'residual'
    model.controls.automatic_profile = True
    model.reset()
    rows = []
    count = round(seconds/.002)
    for index in range(count+1):
        if index % sample_steps == 0:
            reading = model.readings()
            row = {key: reading[key] for key in FIELDS if key != 'time'}
            row['time'] = model.state.time
            rows.append(row)
        if index < count:
            model.step(.002)
    return model, rows


def operating_point(rows, state, frequency=None):
    candidates = [row for row in rows if row['sequence_state'] == state]
    if frequency is not None:
        candidates = [row for row in candidates
                      if abs(row['stator_frequency_command']-frequency) <= .05]
    if not candidates:
        return None
    return candidates[-1]


def classification(row, parameters):
    if row is None:
        return 'not reached'
    if row['runaway'] or row['fault']:
        return 'unstable/runaway'
    command=row['stator_frequency_command']
    if command and abs(row['bus_frequency']-command)>max(.5,.05*command):
        return 'frequency-control-limited'
    if row['vf_current_limited']:
        return 'current-limited'
    if row['vf_flux_limited']:
        return 'flux-limited'
    if row['electrical_export'] <= row['machine_copper_loss'] or row['dc_input_power'] <= 1:
        return 'power-transfer-limited'
    return 'healthy'


def svg(rows, path):
    traces = (
        ('Electrical frequency [Hz]', (('command', 'stator_frequency_command', 1),
                                       ('actual bus', 'bus_frequency', 1))),
        ('Load speed [m/min]', (('speed', 'velocity', 60),)),
        ('Motor current [A RMS]', (('current', 'machine_line_current', 1),)),
        ('Flux [Wb turn]', (('flux', 'flux_magnitude', 1),)),
        ('Generating torque [N m]', (('torque', 'motor_torque', -1),)),
        ('Machine copper loss [W]', (('copper', 'machine_copper_loss', 1),)),
        ('AC power [W / var]', (('P export', 'electrical_export', 1),
                                ('Q demand', 'machine_reactive_demand', 1))),
        ('DC link [V]', (('Vdc', 'dc_voltage', 1),)),
        ('Brake resistor [W]', (('resistor', 'dc_brake_power', 1),)),
        ('Brake command / state', (('release command', '_brake_command', 1),
                                   ('released state', '_brake_state', 1))),
    )
    plot_rows = []
    for row in rows:
        copy = dict(row)
        copy['_brake_command'] = 1 if row['brake_command'] == 'RELEASE' else 0
        copy['_brake_state'] = 1 if row['brake_physical_state'] == 'RELEASED' else 0
        plot_rows.append(copy)
    width, height = 1200, 1280
    left, right, top, panel_height = 95, 1170, 42, 92
    colors = ('#55d6be', '#ffbd66')
    duration = max(row['time'] for row in plot_rows)
    x = lambda value: left + (right-left)*value/max(duration, 1e-12)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="#0f1b2d"/>',
           '<style>text{font-family:Segoe UI,Arial;fill:#dce8f5}.label{font-size:13px}.title{font-size:19px;font-weight:600}</style>',
           '<text x="95" y="25" class="title">Canonical 300 kg automatic lowering sequence</text>']
    for index, (title, series) in enumerate(traces):
        y0 = top + index*121
        values = [row[key]*scale for _, key, scale in series for row in plot_rows]
        lo, hi = min(0, min(values)), max(values)
        if hi-lo < 1e-12:
            hi = lo+1
        y = lambda value: y0+panel_height-(value-lo)/(hi-lo)*panel_height
        out.append(f'<rect x="{left}" y="{y0}" width="{right-left}" height="{panel_height}" fill="#13243a" stroke="#354b65"/>')
        out.append(f'<text x="{left}" y="{y0-7}" class="label">{title}</text>')
        for trace_index, (label, key, scale) in enumerate(series):
            points = ' '.join(f'{x(row["time"]):.2f},{y(row[key]*scale):.2f}' for row in plot_rows)
            color = colors[trace_index]
            out.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
            out.append(f'<text x="{left+170*trace_index}" y="{y0+14}" class="label" fill="{color}">{label}</text>')
    out.append('</svg>')
    path.write_text('\n'.join(out)+'\n', encoding='utf-8')


def report(mode, model, rows):
    state_for_frequency = {20: 'LOWERING', 10: 'SLOWDOWN_1', 5: 'SLOWDOWN_2'}
    final = rows[-1]
    lines = [f'# Canonical {mode} lowering review', '']
    if mode == 'exciter':
        points = [(frequency, operating_point(rows, state, frequency))
                  for frequency, state in state_for_frequency.items()]
        lines.extend([
            '| Target | Status | Actual f [Hz] | Speed [m/min] | Rotor [rpm] | Sync [rpm] | Slip | V LL [V] | I line [A] | I active [A] | I reactive [A] | Flux target / actual / max [Wb] | Torque [N m] |',
            '|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|'])
        for frequency, row in points:
            if row is None:
                lines.append(f'| {frequency} Hz | not reached | - | - | - | - | - | - | - | - | - | - | - |')
                continue
            lines.append(f'| {frequency} Hz | {classification(row, model.parameters)} | {row["bus_frequency"]:.2f} | {60*row["velocity"]:.3f} | {row["rpm"]:.2f} | {row["synchronous_rpm"]:.2f} | {row["slip"]:.4f} | {row["line_voltage"]:.2f} | {row["machine_line_current"]:.3f} | {row["machine_active_current"]:.3f} | {row["machine_reactive_current"]:.3f} | {row["flux_target"]:.3f} / {row["flux_magnitude"]:.3f} / {row["maximum_flux"]:.3f} | {row["motor_torque"]:.3f} |')
        lines.extend(['',
            '| Target | Mechanical in [W] | Copper [W] | Core [W] | Magnetic storage [W] | AC export [W] | Q demand [var] | Rectifier AC [W] | DC in [W] | Vdc [V] | DC capacitor [W] | Resistor [W] |',
            '|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|'])
        for frequency, row in points:
            if row is None:
                lines.append(f'| {frequency} Hz | - | - | - | - | - | - | - | - | - | - | - |')
                continue
            lines.append(f'| {frequency} Hz | {-row["motor_shaft_power"]:.2f} | {row["machine_copper_loss"]:.2f} | {row["machine_core_loss"]:.2f} | {row["magnetic_storage_power"]:.2f} | {row["electrical_export"]:.2f} | {row["machine_reactive_demand"]:.2f} | {row["rectifier_power"]:.2f} | {row["dc_input_power"]:.2f} | {row["dc_voltage"]:.2f} | {row["dc_capacitor_power"]:.2f} | {row["dc_brake_power"]:.2f} |')
    else:
        row = operating_point(rows, 'LOWERING') or rows[-1]
        trajectory_status=('unstable/runaway' if rows[-1]['fault'] or rows[-1]['runaway']
                           else classification(row, model.parameters))
        lines.extend(['', 'Capacitor-only frequency is emergent; no 20/10/5 Hz commands are applied.', '',
                      f'- Natural trajectory status: {trajectory_status}',
                      f'- Speed: {60*row["velocity"]:.3f} m/min; rotor: {row["rpm"]:.2f} rpm; electrical frequency: {row["bus_frequency"]:.2f} Hz; slip: {row["slip"]:.4f}',
                      f'- Voltage/current/flux: {row["line_voltage"]:.2f} V LL / {row["machine_line_current"]:.3f} A / {row["flux_magnitude"]:.3f} Wb',
                      f'- Motor active/reactive current: {row["machine_active_current"]:.3f} / {row["machine_reactive_current"]:.3f} A',
                      f'- Capacitor current/Q: {row["capacitor_line_current"]:.3f} A / {row["capacitor_reactive_supply"]:.2f} var',
                      f'- Generating torque/mechanical input: {-row["motor_torque"]:.3f} N m / {-row["motor_shaft_power"]:.2f} W',
                      f'- Copper/core/magnetic-storage power: {row["machine_copper_loss"]:.2f} / {row["machine_core_loss"]:.2f} / {row["magnetic_storage_power"]:.2f} W',
                      f'- Export/rectifier/DC/resistor: {row["electrical_export"]:.2f} / {row["rectifier_power"]:.2f} / {row["dc_input_power"]:.2f} / {row["dc_brake_power"]:.2f} W',
                      f'- Chopper duty: {100*row["chopper_duty"]:.2f}%',
                      f'- DC link/capacitor power: {row["dc_voltage"]:.2f} V / {row["dc_capacitor_power"]:.2f} W'])
    if mode == 'exciter':
        reached=[row for _,row in points if row is not None]
        max_flux=max(row['flux_magnitude'] for row in rows)
        max_current=max(row['machine_line_current'] for row in rows)
        lines.extend(['', '## Controller audit', '',
                      '- `flux_target` and `flux_magnitude` are the same quantity: peak per-phase magnetizing flux linkage. The target is derived from line-line RMS V/Hz using `sqrt(2/3)/(2 pi)`, so the former 0.95 versus 1.204 discrepancy was real overflux, not an RMS/peak or line/phase mismatch.',
                      '- Stator-resistance compensation now projects the winding-current phasor onto the induced-voltage axis. It adds voltage for motoring active current, subtracts it for generating active current, and does not treat quadrature magnetizing current as a resistive boost.',
                      '- Normal target-flux PI regulation is separate from current/overflux/modulation protection. Protection derating starts only near the configured maximum and cannot redefine the displayed target.',
                      '- The trace logs base voltage, signed resistance compensation, PI correction, unlimited/final voltage, flux error/integral, every limiter, actual bus frequency, active/reactive power, DC-link behavior, contactors, brake state, and faults at 10 ms intervals.', '',
                      f'Observed maxima: {max_flux:.3f} Wb-turn flux and {max_current:.3f} A RMS current.'])
        if reached and any(classification(row,model.parameters)=='frequency-control-limited'
                           for row in reached):
            lines.extend(['',
                'Conclusion: flux regulation no longer causes the slowdown failure, but the retained scalar source does not establish the requested low electrical frequency in this generating/passive-DC plant. The command reaches its scheduled values while actual bus frequency remains set mainly by rotor motion. Independently initialized machine equilibria exist, but below the present DC-link/chopper operating point the rectifier cannot sustain the required braking load; the capacitor charges, braking torque collapses, and the plant moves away. This is a controller-authority/DC-energy-absorption limit of the present architecture, not proof that a commanded point is stable.'])
        elif final['fault']:
            lines.extend(['',f'Conclusion: the sequence ended on `{final["fault"]}`; no unreached target is reported as a success.'])
        else:
            lines.extend(['','Conclusion: all reported points met the frequency-tracking criterion in this run.'])
    elif mode == 'capacitor' and final['fault']:
        lines.extend(['',
                      'Conclusion: this passive capacitance does not reach a safe stable lowering equilibrium before protection acts.'])
    lines.extend(['', f'- Final state: `{final["sequence_state"]}`; fault: `{final["fault"] or "NONE"}`',
                  f'- Final energy residual: {final["energy_residual"]:+.8f} J'])
    return '\n'.join(lines)+'\n'


def main():
    root = Path(__file__).resolve().parents[1]
    docs = root/'docs'
    requested = tuple(sys.argv[1:])
    if any(mode not in ('exciter', 'capacitor') for mode in requested):
        raise SystemExit('usage: python -m simulation.automatic_sequence [exciter|capacitor]')
    modes = requested or ('exciter', 'capacitor')
    summary_path = docs/'automatic-sequence-summary.json'
    summaries = (json.loads(summary_path.read_text(encoding='utf-8'))
                 if requested and summary_path.exists() else {})
    for mode in modes:
        print(f'Running canonical {mode} sequence...', flush=True)
        model, rows = run(mode)
        csv_path = docs/f'automatic-sequence-{mode}.csv'
        with csv_path.open('w', newline='', encoding='utf-8') as handle:
            writer = DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader(); writer.writerows(rows)
        if mode == 'exciter':
            svg(rows, docs/'automatic-sequence.svg')
        text = report(mode, model, rows)
        (docs/f'automatic-sequence-{mode}.md').write_text(text, encoding='utf-8')
        summaries[mode] = {'final_state': rows[-1]['sequence_state'],
                           'fault': rows[-1]['fault'],
                           'energy_residual': rows[-1]['energy_residual']}
        print(text)
    summary_path.write_text(json.dumps(summaries, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
