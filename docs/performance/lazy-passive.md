# Simulation performance lazy-passive

| Case | Simulated [s] | Wall [s] | Real-time factor | Outer steps | Electrical substeps | Derivatives | AC solves | Solver iterations avg / max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed-exciter-20hz | 10.000 | 91.527 | 0.1093 | 5001 | 109411 | 547271 | 526730 | 3.290 / 12 |

## Inclusive subsystem timings

Timings overlap: for example AC-bus solver time is included in `Kernel.rate`, and both are included in integration time.

| Case | Integration | Kernel.rate | Machine currents | AC solver | Rectifier | DC link | Controllers | Readings | Energy diagnostics | Replay frames |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed-exciter-20hz | 90.702 | 74.601 | 3.836 | 61.025 | 9.389 | 1.086 | 0.555 | 0.805 | 0.187 | 0.007560 |

Reference histories are stored beside this report at 10 ms intervals.
