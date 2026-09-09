# Canonical exciter lowering review

| Target | Status | Speed [m/min] | Rotor [rpm] | Sync [rpm] | Slip | V LL [V] | I line [A] | I active [A] | I reactive [A] | Flux / max [Wb] | Torque [N m] |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 Hz | flux-limited | 13.015 | 1242.80 | 1176.64 | -0.0562 | 376.24 | 3.203 | -1.122 | 3.000 | 1.204 / 1.300 | -8.389 |
| 10 Hz | not reached | - | - | - | - | - | - | - | - | - | - |
| 5 Hz | not reached | - | - | - | - | - | - | - | - | - | - |

| Target | Mechanical in [W] | Copper [W] | Core [W] | Magnetic storage [W] | AC export [W] | Q demand [var] | Rectifier AC [W] | DC in [W] | Vdc [V] | DC capacitor [W] | Resistor [W] |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 Hz | 1091.77 | 294.53 | 35.39 | 30.59 | 731.26 | 1955.02 | 731.26 | 696.13 | 500.49 | 453.03 | 93.10 |
| 10 Hz | - | - | - | - | - | - | - | - | - | - | - |
| 5 Hz | - | - | - | - | - | - | - | - | - | - | - |

Conclusion: the retained scalar V/f setup is usable at 20 Hz, but the automatic slowdown did not complete. Protection tripped on `MACHINE OVERFLUX` before 10 Hz settled, so both 10 Hz and 5 Hz are physical validation failures rather than zero-filled successes.

- Final state: `FAULT`; fault: `MACHINE OVERFLUX`
- Final energy residual: +0.00039852 J
