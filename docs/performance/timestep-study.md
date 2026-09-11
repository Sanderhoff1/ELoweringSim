# RK4 electrical-timestep convergence

| Mode | Maximum step [ms] | Wall [s] | RTF | Rejected | Max peak difference | Max final difference | Event shift [ms] | Energy residual [J] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| canonical-exciter | 0.050 | 54.546 | 0.0733 | 1491 | 0.0031% | 0.0022% | 0.000 | +0.00002102 |
| canonical-exciter | 0.100 | 34.059 | 0.1174 | 4705 | 0.0000% | 0.0000% | 0.000 | +0.00002082 |
| canonical-exciter | 0.200 | 23.594 | 0.1695 | 6355 | 0.0028% | 0.0019% | 0.000 | +0.00000237 |
| canonical-exciter | 0.400 | 18.293 | 0.2187 | 7162 | 0.0463% | 0.0516% | 4.000 | -0.00004973 |
| capacitor-only | 0.020 | 16.226 | 0.1233 | 0 | 26.3581% | 14.6141% | 0.000 | +0.00000205 |
| capacitor-only | 0.050 | 8.076 | 0.2476 | 2091 | 0.0000% | 0.0000% | 0.000 | +0.00015676 |
| capacitor-only | 0.100 | 8.013 | 0.2496 | 2091 | 0.0000% | 0.0000% | 0.000 | +0.00015676 |
| capacitor-only | 0.200 | 8.101 | 0.2469 | 2091 | 0.0000% | 0.0000% | 0.000 | +0.00015676 |

The production default remains 0.1 ms unless a larger candidate meets all engineering tolerances in both full reference runs.
