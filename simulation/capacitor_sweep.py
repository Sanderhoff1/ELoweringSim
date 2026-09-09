"""Capacitance sensitivity review for the passive self-excited mode."""
from csv import DictWriter
from pathlib import Path

from .automatic_sequence import run


CAPACITANCES = (3.0, 4.5, 6.0, 7.5, 9.0)
FIELDS = ('capacitance', 'self_excited', 'classification', 'time', 'velocity',
          'rpm', 'bus_frequency', 'slip', 'line_voltage', 'machine_line_current',
          'machine_active_current', 'machine_reactive_current',
          'capacitor_line_current', 'capacitor_reactive_supply', 'flux_magnitude',
          'machine_copper_loss', 'machine_core_loss', 'electrical_export',
          'rectifier_power', 'dc_input_power', 'dc_voltage', 'chopper_duty',
          'dc_brake_power', 'acceleration', 'fault', 'energy_residual')


def natural_row(rows):
    natural = [row for row in rows
               if row['sequence_state'] in ('LOWERING', 'BRAKE_APPLY')
               and not row['fault']]
    return max(natural, key=lambda row: row['line_voltage']) if natural else rows[-1]


def classify(row, parameters, final):
    if final['fault'] == 'MACHINE OVERFLUX' or row['flux_magnitude'] > parameters.maximum_magnetic_flux:
        return 'over-fluxed'
    if final['fault'] == 'MACHINE OVERCURRENT':
        return 'current-limited / thermally problematic'
    if final['fault'] == 'RUNAWAY DIAGNOSTIC' or final['runaway']:
        return 'runaway'
    if row['line_voltage'] < 25 or row['flux_magnitude'] < .05:
        return 'insufficiently excited'
    if row['machine_line_current'] > parameters.motor_current_limit_rms:
        return 'current-limited / thermally problematic'
    if row['electrical_export'] <= row['machine_copper_loss'] or row['dc_input_power'] <= 1:
        return 'unable to transfer sufficient real power'
    if abs(row['acceleration']) < .02:
        return 'stable'
    if abs(row['acceleration']) < .08:
        return 'weakly stable'
    return 'runaway'


def sweep(seconds=8.0):
    results = []
    for capacitance in CAPACITANCES:
        print(f'Running capacitor-only case at {capacitance:g} uF/branch...',
              flush=True)
        model, rows = run('capacitor', seconds=seconds, sample_steps=10,
                          changes={'capacitor_capacitance': capacitance})
        row = natural_row(rows)
        result = {key: row.get(key, '') for key in FIELDS}
        result['capacitance'] = capacitance
        result['self_excited'] = any(sample['line_voltage'] >= 25 and
                                     sample['flux_magnitude'] >= .05
                                     for sample in rows)
        result['classification'] = classify(row, model.parameters, rows[-1])
        results.append(result)
    return results


def markdown(results):
    lines = [
        '# Capacitor-only parameter sweep', '',
        'No frequency or voltage target is imposed. Each row is the strongest '
        'naturally excited pre-fault/brake sample for the same 300 kg common plant; '
        'the status is based on the complete trajectory.', '',
        '| C delta [uF] | Excited | Status | f [Hz] | Speed [m/min] | V LL [V] | I motor [A] | I cap [A] | Flux [Wb] | Cu / core [W] | Export / DC [W] | Vdc [V] | Resistor [W] |',
        '|---:|:---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in results:
        lines.append(
            f'| {row["capacitance"]:g} | {"yes" if row["self_excited"] else "no"} | '
            f'{row["classification"]} | {row["bus_frequency"]:.2f} | '
            f'{60*row["velocity"]:.2f} | {row["line_voltage"]:.1f} | '
            f'{row["machine_line_current"]:.2f} | {row["capacitor_line_current"]:.2f} | '
            f'{row["flux_magnitude"]:.3f} | {row["machine_copper_loss"]:.1f} / '
            f'{row["machine_core_loss"]:.1f} | {row["electrical_export"]:.1f} / '
            f'{row["dc_input_power"]:.1f} | {row["dc_voltage"]:.1f} | '
            f'{row["dc_brake_power"]:.1f} |')
    lines.extend(['', 'Classification uses the complete trajectory: any over-flux or '
                  'runaway fault overrides an apparently acceptable pre-fault sample.'])
    return '\n'.join(lines)+'\n'


def main():
    results = sweep()
    docs = Path(__file__).resolve().parents[1]/'docs'
    with (docs/'capacitor-sweep.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)
    text = markdown(results)
    (docs/'capacitor-sweep.md').write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
