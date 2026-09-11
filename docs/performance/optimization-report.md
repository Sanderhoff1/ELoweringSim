# Simulation optimization report

## Outcome

The production model retains RK4 and its 0.1 ms maximum electrical step. The optimized implementation produces the same final sequence states and faults as the preserved reference histories.

| Case | Before wall [s] | After wall [s] | Speedup | Before / after real-time factor |
|---|---:|---:|---:|---:|
| canonical-exciter | 504.228 | 236.151 | 2.14x | 0.0278 / 0.0593 |
| capacitor-only | 40.828 | 31.151 | 1.31x | 0.1959 / 0.2568 |
| fixed-exciter-20hz | 299.784 | 114.671 | 2.61x | 0.0334 / 0.0872 |

## Reference-history comparison

Histories use identical 10 ms sampling. Peak errors compare absolute maxima over the full run. Event shifts therefore have 10 ms measurement resolution.

| Case | Worst selected peak error | Largest event shift | Final energy residual before / after | Final state and fault |
|---|---:|---:|---:|---|
| canonical-exciter | 0.0000% (line_voltage) | 0 ms | 0.000179481 / 0.000179465 | STOPPED; no fault |
| capacitor-only | 0.0000% (motor_torque) | 0 ms | 0.000156726 / 0.000156726 | FAULT; RUNAWAY DIAGNOSTIC |
| fixed-exciter-20hz | 0.0000% (flux_magnitude) | 0 ms | 1.25318e-05 / 1.25704e-05 | LOWERING; no fault |

The fixed-exciter final two-second operating-point averages provide the cleanest steady-state comparison:

| Quantity | Before | After | Relative difference |
|---|---:|---:|---:|
| velocity | 0.237172578 | 0.237172578 | 0.000000% |
| rpm | 1358.89878 | 1358.89878 | 0.000000% |
| line_voltage | 323.622645 | 323.622645 | 0.000000% |
| machine_line_current | 1.68705914 | 1.68705914 | 0.000000% |
| machine_active_current | -0.860158818 | -0.860158819 | 0.000000% |
| machine_reactive_current | 1.45130702 | 1.45130701 | 0.000000% |
| flux_magnitude | 0.952070946 | 0.952070946 | 0.000000% |
| motor_torque | -4.16966715 | -4.16966715 | 0.000000% |
| electrical_export | 482.145675 | 482.145676 | 0.000000% |
| machine_reactive_demand | 813.502252 | 813.502252 | 0.000000% |
| machine_copper_loss | 85.0336696 | 85.0336696 | 0.000000% |
| machine_core_loss | 26.1829048 | 26.1829048 | 0.000000% |
| rectifier_power | 482.145675 | 482.145676 | 0.000000% |
| dc_input_power | 460.721033 | 460.721033 | 0.000000% |
| dc_voltage | 432.510601 | 432.510601 | 0.000000% |
| dc_brake_power | 460.705598 | 460.705598 | 0.000000% |
| battery_power | 5.08871461 | 5.0887146 | 0.000000% |
| aux_voltage | 599.618126 | 599.618126 | 0.000000% |
| aux_power | 0.000122574904 | 0.000122574872 | 0.000026% |

## Acceptance tolerances

The acceptance limits were fixed before selecting production changes: steady speed 0.5%; steady RMS current, AC voltage, flux, and power flows 1%; transient current, voltage, and flux peaks 2%; event timing one 2 ms controller interval; and the existing 0.002 J whole-system residual limit. The final histories meet these limits: sampled events are identical, selected peak differences round to 0.0000%, steady differences round to 0.000000%, and the full validation suite confirms the residual bound.

## Where time went

| Case | AC solver before / after [s] | Rectifier before / after [s] | Auxiliary/DC-link before / after [s] | Replay frames after [s] |
|---|---:|---:|---:|---:|
| canonical-exciter | 125.835 / 110.631 | 154.126 / 36.247 | 2.286 / 2.362 | 0.012520 |
| capacitor-only | 0.000 / 0.000 | 0.288 / 0.298 | 0.885 / 0.873 | 0.006999 |
| fixed-exciter-20hz | 108.216 / 87.131 | 102.723 / 13.733 | 1.133 / 1.098 | 0.008232 |

## Independently measured optimization

| Change | Workload | Before / after | Speedup |
|---|---|---:|---:|
| Exact auxiliary quadratic root | 100,000 representative link solves | 3.870 / 0.281 s | 13.77x |

The solver changes are intentionally reported as a combined final benchmark because continuation, lazy passive seeding, and cached residual evaluation interact; assigning overlapping speedups to them would be misleading. Intermediate experimental reports are retained for audit, but include candidates later rejected on behavior.

## Accepted changes

- Reuse the immediately previous terminal voltage as a continuation seed before the broad bounded AC search.
- Compute the expensive passive bridge seed only when the continuation solve fails or the converter is disabled.
- Reuse exact network evaluations within a solve and stop passive-seed bisection at useful floating-point precision.
- Replace the auxiliary-link 70-iteration bisection with the algebraically identical positive quadratic root.
- Precompute immutable coefficients and skip converter-only work when the converter is disabled.

## Architecture audits

- Physics does not call `readings()` or full diagnostics per derivative. Controllers/state logic run on the 2 ms outer step, telemetry is sampled at 10 ms in this harness, and replay frames contain data rather than model copies.
- A short allocation trace reached only 10.4 kB peak live traced memory. Existing mechanical-state `replace()` snapshots are required for rejected-step rollback; the only `copy.copy()` calls are in replay display-context construction, outside physics.
- Discrete controller/contactor/brake changes already occur at explicit outer-step boundaries. Landing logic splits the physical step at impact; no smaller global timestep is imposed merely to poll events.
- Energy accumulators needed for conservation remain coupled to accepted physical substeps; report-only diagnostics stay at telemetry cadence.

## Investigated but rejected

- A 0.2 ms production step passed sampled electrical comparisons but moved a position-triggered automatic-profile checkpoint; production remains at 0.1 ms.
- RK2 gave little wall-time improvement and larger event/residual errors; production remains RK4.
- Forward-difference Jacobians were faster but accumulated enough trajectory bias to move the same behavioral checkpoint; central differences remain.
- Adaptive/semi-implicit stepping was not adopted across discontinuous limiter and switching regions.
- NumPy/Numba compilation was not adopted: neither dependency is present, and the hot solver is branch-heavy complex scalar code with Python closures.
- Parallel core stepping was not adopted because the plant is a causally coupled time trajectory. Independent benchmark sweeps may be run in separate processes.
- Telemetry, controller, energy-accounting, and replay construction were already decoupled or negligible compared with integration; changing their cadence would not justify added behavior risk.

## Final validation

- `python -m unittest discover -s simulation/tests -v`: 147 tests passed in 441.468 s.
- Both canonical histories were regenerated: exciter finished `STOPPED` without a fault; capacitor-only produced the expected `RUNAWAY DIAGNOSTIC` fault.
- Replay serialization, checksum, reconstruction, lightweight-frame, and UI playback tests passed as part of the full suite.
- A final compile check and five focused auxiliary/solver tests passed after code cleanup.

Raw reports, JSON counters, reference histories, timestep results, and integrator results are in this directory.
