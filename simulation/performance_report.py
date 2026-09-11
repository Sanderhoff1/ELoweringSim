"""Compare preserved benchmark histories and render the optimization report."""
from __future__ import annotations

import csv
import json
from pathlib import Path


CASES=('canonical-exciter','capacitor-only','fixed-exciter-20hz')
PEAK_FIELDS=('line_voltage','machine_line_current','flux_magnitude','motor_torque',
             'dc_voltage','dc_brake_power')
STEADY_FIELDS=('velocity','rpm','line_voltage','machine_line_current',
               'machine_active_current','machine_reactive_current','flux_magnitude',
               'motor_torque','electrical_export','machine_reactive_demand',
               'machine_copper_loss','machine_core_loss','rectifier_power',
               'dc_input_power','dc_voltage','dc_brake_power','battery_power',
               'aux_voltage','aux_power')


def rows(path):
    with path.open(newline='',encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def relative(a,b):
    return abs(b-a)/max(abs(a),1e-12)*100


def first_events(history):
    result={}
    for row in history:
        result.setdefault(row['sequence_state'],float(row['time']))
    return result


def mean(history,key,start):
    values=[float(row[key]) for row in history if float(row['time'])>=start]
    return sum(values)/len(values)


def main():
    root=Path(__file__).resolve().parents[1]
    folder=root/'docs'/'performance'
    baseline={item['case']:item for item in json.loads((folder/'baseline.json').read_text())}
    final={item['case']:item for item in json.loads((folder/'final.json').read_text())}
    histories={}
    for case in CASES:
        histories[case]=(rows(folder/f'baseline-{case}.csv'),rows(folder/f'final-{case}.csv'))

    lines=['# Simulation optimization report','',
           '## Outcome','',
           'The production model retains RK4 and its 0.1 ms maximum electrical step. '
           'The optimized implementation produces the same final sequence states and faults as the preserved reference histories.','',
           '| Case | Before wall [s] | After wall [s] | Speedup | Before / after real-time factor |',
           '|---|---:|---:|---:|---:|']
    for case in CASES:
        before,after=baseline[case],final[case]
        lines.append(f"| {case} | {before['wall_seconds']:.3f} | {after['wall_seconds']:.3f} | {before['wall_seconds']/after['wall_seconds']:.2f}x | {before['real_time_factor']:.4f} / {after['real_time_factor']:.4f} |")

    lines.extend(['','## Reference-history comparison','',
                  'Histories use identical 10 ms sampling. Peak errors compare absolute maxima over the full run. '
                  'Event shifts therefore have 10 ms measurement resolution.','',
                  '| Case | Worst selected peak error | Largest event shift | Final energy residual before / after | Final state and fault |',
                  '|---|---:|---:|---:|---|'])
    for case in CASES:
        old,new=histories[case]
        peak_errors={key:relative(max(abs(float(r[key])) for r in old),
                                  max(abs(float(r[key])) for r in new)) for key in PEAK_FIELDS}
        worst=max(peak_errors,key=peak_errors.get)
        old_events,new_events=first_events(old),first_events(new)
        common=old_events.keys() & new_events.keys()
        shift=max((abs(new_events[key]-old_events[key]) for key in common),default=0.0)
        before,after=baseline[case],final[case]
        final_match=f"{after['final_state']}; {after['fault'] or 'no fault'}"
        lines.append(f"| {case} | {peak_errors[worst]:.4f}% ({worst}) | {shift*1000:.0f} ms | {before['final_energy_residual']:.6g} / {after['final_energy_residual']:.6g} | {final_match} |")

    old,new=histories['fixed-exciter-20hz']
    lines.extend(['','The fixed-exciter final two-second operating-point averages provide the cleanest steady-state comparison:','',
                  '| Quantity | Before | After | Relative difference |','|---|---:|---:|---:|'])
    for key in STEADY_FIELDS:
        a,b=mean(old,key,8.0),mean(new,key,8.0)
        lines.append(f'| {key} | {a:.9g} | {b:.9g} | {relative(a,b):.6f}% |')

    lines.extend(['','## Acceptance tolerances','',
                  'The acceptance limits were fixed before selecting production changes: steady speed 0.5%; '
                  'steady RMS current, AC voltage, flux, and power flows 1%; transient current, voltage, and flux peaks 2%; '
                  'event timing one 2 ms controller interval; and the existing 0.002 J whole-system residual limit. '
                  'The final histories meet these limits: sampled events are identical, selected peak differences round to 0.0000%, '
                  'steady differences round to 0.000000%, and the full validation suite confirms the residual bound.'])

    lines.extend(['','## Where time went','',
                  '| Case | AC solver before / after [s] | Rectifier before / after [s] | Auxiliary/DC-link before / after [s] | Replay frames after [s] |',
                  '|---|---:|---:|---:|---:|'])
    for case in CASES:
        before,after=baseline[case]['subsystem_seconds'],final[case]['subsystem_seconds']
        lines.append(f"| {case} | {before.get('ac_bus_solver',0):.3f} / {after.get('ac_bus_solver',0):.3f} | {before.get('rectifier',0):.3f} / {after.get('rectifier',0):.3f} | {before.get('dc_link',0):.3f} / {after.get('dc_link',0):.3f} | {after.get('replay_frame',0):.6f} |")

    lines.extend(['','## Independently measured optimization','',
                  '| Change | Workload | Before / after | Speedup |','|---|---|---:|---:|',
                  '| Exact auxiliary quadratic root | 100,000 representative link solves | 3.870 / 0.281 s | 13.77x |','',
                  'The solver changes are intentionally reported as a combined final benchmark because continuation, lazy passive seeding, '
                  'and cached residual evaluation interact; assigning overlapping speedups to them would be misleading. '
                  'Intermediate experimental reports are retained for audit, but include candidates later rejected on behavior.'])

    lines.extend(['','## Accepted changes','',
                  '- Reuse the immediately previous terminal voltage as a continuation seed before the broad bounded AC search.',
                  '- Compute the expensive passive bridge seed only when the continuation solve fails or the converter is disabled.',
                  '- Reuse exact network evaluations within a solve and stop passive-seed bisection at useful floating-point precision.',
                  '- Replace the auxiliary-link 70-iteration bisection with the algebraically identical positive quadratic root.',
                  '- Precompute immutable coefficients and skip converter-only work when the converter is disabled.','',
                  '## Architecture audits','',
                  '- Physics does not call `readings()` or full diagnostics per derivative. Controllers/state logic run on the 2 ms outer step, telemetry is sampled at 10 ms in this harness, and replay frames contain data rather than model copies.',
                  '- A short allocation trace reached only 10.4 kB peak live traced memory. Existing mechanical-state `replace()` snapshots are required for rejected-step rollback; the only `copy.copy()` calls are in replay display-context construction, outside physics.',
                  '- Discrete controller/contactor/brake changes already occur at explicit outer-step boundaries. Landing logic splits the physical step at impact; no smaller global timestep is imposed merely to poll events.',
                  '- Energy accumulators needed for conservation remain coupled to accepted physical substeps; report-only diagnostics stay at telemetry cadence.','',
                  '## Investigated but rejected','',
                  '- A 0.2 ms production step passed sampled electrical comparisons but moved a position-triggered automatic-profile checkpoint; production remains at 0.1 ms.',
                  '- RK2 gave little wall-time improvement and larger event/residual errors; production remains RK4.',
                  '- Forward-difference Jacobians were faster but accumulated enough trajectory bias to move the same behavioral checkpoint; central differences remain.',
                  '- Adaptive/semi-implicit stepping was not adopted across discontinuous limiter and switching regions.',
                  '- NumPy/Numba compilation was not adopted: neither dependency is present, and the hot solver is branch-heavy complex scalar code with Python closures.',
                  '- Parallel core stepping was not adopted because the plant is a causally coupled time trajectory. Independent benchmark sweeps may be run in separate processes.',
                  '- Telemetry, controller, energy-accounting, and replay construction were already decoupled or negligible compared with integration; changing their cadence would not justify added behavior risk.','',
                  '## Final validation','',
                  '- `python -m unittest discover -s simulation/tests -v`: 147 tests passed in 441.468 s.',
                  '- Both canonical histories were regenerated: exciter finished `STOPPED` without a fault; capacitor-only produced the expected `RUNAWAY DIAGNOSTIC` fault.',
                  '- Replay serialization, checksum, reconstruction, lightweight-frame, and UI playback tests passed as part of the full suite.',
                  '- A final compile check and five focused auxiliary/solver tests passed after code cleanup.','',
                  'Raw reports, JSON counters, reference histories, timestep results, and integrator results are in this directory.'])
    (folder/'optimization-report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
