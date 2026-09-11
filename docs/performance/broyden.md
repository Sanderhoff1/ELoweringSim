# Simulation performance broyden

| Case | Simulated [s] | Wall [s] | Real-time factor | Outer steps | Electrical substeps | Derivatives | AC solves | Solver iterations avg / max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed-exciter-20hz | 10.000 | 91.720 | 0.1090 | 5001 | 115009 | 572374 | 555874 | 3.787 / 15 |

## Inclusive subsystem timings

Timings overlap: for example AC-bus solver time is included in `Kernel.rate`, and both are included in integration time.

| Case | Integration | Kernel.rate | Machine currents | AC solver | Rectifier | DC link | Controllers | Readings | Energy diagnostics | Replay frames |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed-exciter-20hz | 90.893 | 73.461 | 4.133 | 58.140 | 8.161 | 1.154 | 0.564 | 0.807 | 0.188 | 0.008133 |

Reference histories are stored beside this report at 10 ms intervals.
