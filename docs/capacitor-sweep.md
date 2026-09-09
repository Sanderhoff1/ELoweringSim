# Capacitor-only parameter sweep

No frequency or voltage target is imposed. Each row is the strongest naturally excited pre-fault/brake sample for the same 300 kg common plant; the status is based on the complete trajectory.

| C delta [uF] | Excited | Status | f [Hz] | Speed [m/min] | V LL [V] | I motor [A] | I cap [A] | Flux [Wb] | Cu / core [W] | Export / DC [W] | Vdc [V] | Resistor [W] |
|---:|:---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3 | yes | runaway | 171.96 | 60.29 | 6.8 | 0.05 | 0.04 | 0.004 | 0.1 / 0.0 | 0.4 / 0.3 | 8.9 | 0.0 |
| 4.5 | yes | runaway | 163.10 | 60.25 | 62.4 | 0.57 | 0.50 | 0.038 | 13.6 / 1.0 | 29.7 / 27.5 | 81.4 | 0.0 |
| 6 | yes | runaway | 152.25 | 59.36 | 252.9 | 2.71 | 2.51 | 0.152 | 307.7 / 16.0 | 447.9 / 413.2 | 332.0 | 0.0 |
| 7.5 | yes | runaway | 136.68 | 54.22 | 477.7 | 5.76 | 5.33 | 0.325 | 1382.7 / 57.1 | 1804.6 / 1676.5 | 622.5 | 1041.6 |
| 9 | yes | current-limited / thermally problematic | 124.13 | 49.80 | 479.2 | 6.30 | 5.83 | 0.365 | 1650.0 / 57.4 | 1981.3 / 1823.9 | 621.4 | 944.9 |

Classification uses the complete trajectory: any over-flux or runaway fault overrides an apparently acceptable pre-fault sample.
