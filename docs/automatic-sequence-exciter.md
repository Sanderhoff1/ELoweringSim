# Canonical exciter lowering review

| Target | Status | Actual f [Hz] | Speed [m/min] | Rotor [rpm] | Sync [rpm] | Slip | V LL [V] | I line [A] | I active [A] | I reactive [A] | Flux target / actual / max [Wb] | Torque [N m] |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 Hz | frequency-control-limited | 38.75 | 12.633 | 1206.40 | 1162.42 | -0.0378 | 318.69 | 1.784 | -0.737 | 1.625 | 0.950 / 1.047 / 1.300 | -4.110 |
| 15 Hz | frequency-control-limited | 35.93 | 11.857 | 1132.26 | 1077.94 | -0.0504 | 265.05 | 1.695 | -0.858 | 1.461 | 0.950 / 0.951 / 1.300 | -4.194 |
| 10 Hz | frequency-control-limited | 39.01 | 12.863 | 1228.32 | 1170.39 | -0.0495 | 280.16 | 1.686 | -0.906 | 1.422 | 0.950 / 0.926 / 1.300 | -4.247 |
| 7.5 Hz | frequency-control-limited | 39.70 | 13.087 | 1249.69 | 1191.02 | -0.0493 | 284.27 | 1.690 | -0.918 | 1.420 | 0.950 / 0.923 / 1.300 | -4.280 |
| 5 Hz | frequency-control-limited | 40.57 | 13.373 | 1277.02 | 1217.25 | -0.0491 | 289.65 | 1.698 | -0.933 | 1.419 | 0.950 / 0.920 / 1.300 | -4.327 |

| Target | Mechanical in [W] | Copper [W] | Core [W] | Magnetic storage [W] | AC export [W] | Q demand [var] | Rectifier AC [W] | DC in [W] | Vdc / target [V] | DC capacitor [W] | Resistor [W] | Duty |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 Hz | 519.18 | 87.17 | 25.39 | -0.18 | 406.79 | 896.77 | 406.79 | 390.34 | 428.13 / 400.00 | 0.48 | 389.86 | 70.2% |
| 15 Hz | 497.23 | 85.58 | 17.56 | -0.00 | 394.09 | 670.87 | 394.09 | 374.07 | 351.31 / 300.00 | 0.07 | 374.00 | 100.0% |
| 10 Hz | 546.33 | 87.09 | 19.62 | 0.08 | 439.54 | 689.90 | 439.54 | 417.23 | 371.37 / 200.00 | -0.69 | 417.92 | 100.0% |
| 7.5 Hz | 560.09 | 88.02 | 20.20 | 0.10 | 451.77 | 698.99 | 451.77 | 428.86 | 376.84 / 150.00 | -1.47 | 430.34 | 100.0% |
| 5 Hz | 578.69 | 89.41 | 20.97 | 0.16 | 468.15 | 711.75 | 468.15 | 444.45 | 384.00 / 100.00 | -2.39 | 446.84 | 100.0% |

Instantaneous real-power checks at the reported points:

- Maximum machine-path mismatch: 0.000000 W.
- Maximum rectifier-path mismatch: 0.000000 W.
- Maximum DC-link-path mismatch: 0.000000 W. Reactive power is excluded.

## Controller audit

- `flux_target` and `flux_magnitude` are the same quantity: peak per-phase magnetizing flux linkage. The target is derived from line-line RMS V/Hz using `sqrt(2/3)/(2 pi)`, so the former 0.95 versus 1.204 discrepancy was real overflux, not an RMS/peak or line/phase mismatch.
- Stator-resistance compensation now projects the winding-current phasor onto the induced-voltage axis. It adds voltage for motoring active current, subtracts it for generating active current, and does not treat quadrature magnetizing current as a resistive boost.
- Normal target-flux PI regulation is separate from current/overflux/modulation protection. Protection derating starts only near the configured maximum and cannot redefine the displayed target.
- The trace logs base voltage, signed resistance compensation, PI correction, unlimited/final voltage, flux error/integral, every limiter, actual bus frequency, active/reactive power, DC-link behavior, contactors, brake state, and faults at 10 ms intervals.

Observed maxima: 1.134 Wb-turn flux and 2.167 A RMS current.

Conclusion: the frequency-derived target removes the previous 500 V power-path blockage: the bridge continues exporting real power and the resistor absorbs it below 500 V. It does not establish the requested low electrical frequencies. The load remains near the higher machine/load/resistor equilibrium and actual frequency is set mainly by rotor motion, not by the scalar command. The reverse-blocking small exciter is at its physical limit: it supplies reactive excitation but cannot absorb generator real power to force the commanded rotating field. From 15 Hz downward the chopper is also at full duty, so lowering its voltage target cannot increase braking torque; the configured resistor and available generator voltage set the maximum absorption. The failure is therefore exciter plus duty/resistor braking-authority saturation, not capacitor charging or forced machine copper loss.

- Final state: `STOPPED`; fault: `NONE`
- Final energy residual: +0.00017947 J
