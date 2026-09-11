# Simulation performance final

| Case | Simulated [s] | Wall [s] | Real-time factor | Outer steps | Electrical substeps | Derivatives | AC solves | Solver iterations avg / max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| canonical-exciter | 14.000 | 236.151 | 0.0593 | 7000 | 265792 | 1272983 | 590924 | 3.304 / 19 |
| capacitor-only | 8.000 | 31.151 | 0.2568 | 4000 | 184182 | 739131 | 0 | 0.000 / 0 |
| fixed-exciter-20hz | 10.000 | 114.671 | 0.0872 | 5001 | 110539 | 552345 | 532006 | 3.263 / 19 |

## Inclusive subsystem timings

Timings overlap: for example AC-bus solver time is included in `Kernel.rate`, and both are included in integration time.

| Case | Integration | Kernel.rate | Machine currents | AC solver | Rectifier | DC link | Controllers | Readings | Energy diagnostics | Replay frames |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| canonical-exciter | 234.691 | 203.400 | 8.590 | 110.631 | 36.247 | 2.362 | 1.168 | 1.428 | 0.324 | 0.012520 |
| capacitor-only | 30.810 | 12.218 | 4.161 | 0.000 | 0.298 | 0.873 | 0.515 | 0.324 | 0.094 | 0.006999 |
| fixed-exciter-20hz | 113.743 | 101.001 | 3.908 | 87.131 | 13.733 | 1.098 | 0.569 | 0.907 | 0.207 | 0.008232 |

Reference histories are stored beside this report at 10 ms intervals.
