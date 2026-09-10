# Scalar V/f independently initialized operating points

Each case starts from the nonlinear T-circuit machine/load torque equilibrium at the requested peak magnetizing-flux target, with the common rectifier/DC plant then integrated dynamically. `Stable` requires both speed settling and actual AC frequency tracking; a command value alone does not qualify.

| Command | Stable | Speed [m/min] | Rotor [rpm] | Actual / command f [Hz] | Slip | V LL [V] | I [A] | Flux target / actual [Wb] | Cu / core [W] | Mechanical / export / DC / resistor [W] | Exciter P / Q |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | no | 14.635 | 1397.5 | 45.22 / 20 | -0.030 | 385.3 | 1.81 | 0.950 / 1.078 | 88.2 / 37.1 | 592.2 / 467.2 / 451.2 / 444.2 | 0.0 / 1117.3 |
| 15 | no | 14.871 | 1420.1 | 45.94 / 15 | -0.030 | 385.5 | 1.78 | 0.950 / 1.062 | 85.9 / 37.2 | 595.2 / 472.4 / 456.1 / 449.0 | 0.0 / 1093.3 |
| 10 | no | 15.497 | 1479.9 | 47.84 / 10 | -0.031 | 386.8 | 1.73 | 0.950 / 1.025 | 82.9 / 37.4 | 616.1 / 496.1 / 478.4 / 471.4 | -0.0 / 1045.1 |
| 7.5 | no | 15.949 | 1523.0 | 49.20 / 7.5 | -0.032 | 387.8 | 1.70 | 0.950 / 1.000 | 81.9 / 37.6 | 635.4 / 516.1 / 497.3 / 490.4 | 0.0 / 1017.0 |
| 5 | no | 16.362 | 1562.5 | 50.46 / 5 | -0.032 | 388.4 | 1.66 | 0.950 / 0.977 | 79.8 / 37.7 | 643.1 / 525.7 / 506.3 / 498.2 | 0.0 / 987.7 |

The isolated T-circuit calculation finds a machine torque equilibrium at every requested frequency, but the scheduled-target test must still demonstrate stability in the complete plant. Continuous power below 500 V is now possible. If duty saturates, the configured resistor and available generated voltage—not the target alone—bound braking power and the plant can move to a higher rotor-speed equilibrium.
