# Simulation performance solver-passive

| Case | Simulated [s] | Wall [s] | Real-time factor | Outer steps | Electrical substeps | Derivatives | AC solves | Solver iterations avg / max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed-exciter-20hz | 10.000 | 170.418 | 0.0587 | 5001 | 109411 | 547271 | 526345 | 3.292 / 12 |

## Inclusive subsystem timings

Timings overlap: for example AC-bus solver time is included in `Kernel.rate`, and both are included in integration time.

| Case | Integration | Kernel.rate | Machine currents | AC solver | Rectifier | DC link | Controllers | Readings | Energy diagnostics | Replay frames |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed-exciter-20hz | 168.887 | 153.059 | 3.871 | 60.924 | 50.817 | 1.112 | 0.572 | 1.510 | 0.322 | 0.007915 |

Reference histories are stored beside this report at 10 ms intervals.
