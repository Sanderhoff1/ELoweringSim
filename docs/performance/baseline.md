# Simulation performance baseline

| Case | Simulated [s] | Wall [s] | Real-time factor | Outer steps | Electrical substeps | Derivatives | AC solves | Solver iterations avg / max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| canonical-exciter | 14.000 | 504.228 | 0.0278 | 7000 | 265782 | 1272938 | 590216 | 3.308 / 19 |
| capacitor-only | 8.000 | 40.828 | 0.1959 | 4000 | 184182 | 739131 | 0 | 0.000 / 0 |
| fixed-exciter-20hz | 10.000 | 299.784 | 0.0334 | 5001 | 110537 | 552336 | 531410 | 3.266 / 19 |

## Inclusive subsystem timings

Timings overlap: for example AC-bus solver time is included in `Kernel.rate`, and both are included in integration time.

| Case | Integration | Kernel.rate | Machine currents | AC solver | Rectifier | DC link | Controllers | Readings | Energy diagnostics | Replay frames |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| canonical-exciter | 501.002 | 463.056 | 8.138 | 125.835 | 154.126 | 2.286 | 1.097 | 3.195 | 0.669 | 0.011781 |
| capacitor-only | 40.478 | 14.150 | 4.347 | 0.000 | 0.288 | 0.885 | 0.512 | 0.332 | 0.096 | 0.006776 |
| fixed-exciter-20hz | 297.337 | 281.507 | 4.057 | 108.216 | 102.723 | 1.133 | 0.601 | 2.426 | 0.511 | 0.008373 |

Reference histories are stored beside this report at 10 ms intervals.
