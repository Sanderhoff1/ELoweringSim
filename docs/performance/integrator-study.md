# Integrator benchmark

| Integrator | Maximum step [ms] | Wall [s] | RTF | Rejected | Max peak difference | Max final difference | Event shift [ms] | Energy residual [J] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RK4 | 0.100 | 34.059 | 0.1174 | 4705 | reference | reference | 0.000 | +0.00002082 |
| RK2 | 0.050 | 33.670 | 0.1188 | 4910 | 0.0898% | 0.0833% | 6.000 | +0.00008632 |
| RK2 | 0.100 | 31.727 | 0.1261 | 24212 | 0.1831% | 0.1582% | 10.000 | +0.00012309 |

Adaptive explicit and semi-implicit replacements were not implemented: discontinuous converter-limit regions and the existing local energy acceptance test make a speculative replacement higher risk than the measured RK4 timestep gain.
