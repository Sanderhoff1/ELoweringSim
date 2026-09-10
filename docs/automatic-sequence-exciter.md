# Canonical exciter lowering review

| Target | Status | Actual f [Hz] | Speed [m/min] | Rotor [rpm] | Sync [rpm] | Slip | V LL [V] | I line [A] | I active [A] | I reactive [A] | Flux target / actual / max [Wb] | Torque [N m] |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 Hz | frequency-control-limited | 45.86 | 14.857 | 1418.78 | 1375.69 | -0.0313 | 381.36 | 1.781 | -0.727 | 1.626 | 0.950 / 1.053 / 1.300 | -4.060 |
| 10 Hz | frequency-control-limited | 54.10 | 17.600 | 1680.72 | 1623.03 | -0.0355 | 392.96 | 1.674 | -0.910 | 1.405 | 0.950 / 0.926 / 1.300 | -4.232 |
| 5 Hz | frequency-control-limited | 54.86 | 17.870 | 1706.44 | 1645.73 | -0.0369 | 394.54 | 1.699 | -0.955 | 1.405 | 0.950 / 0.917 / 1.300 | -4.381 |

| Target | Mechanical in [W] | Copper [W] | Core [W] | Magnetic storage [W] | AC export [W] | Q demand [var] | Rectifier AC [W] | DC in [W] | Vdc [V] | DC capacitor [W] | Resistor [W] |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 Hz | 603.26 | 86.60 | 36.36 | -0.18 | 480.48 | 1074.10 | 480.48 | 463.42 | 515.58 | 0.59 | 312.83 |
| 10 Hz | 744.80 | 86.73 | 38.60 | 0.07 | 619.40 | 956.11 | 619.40 | 594.33 | 527.87 | -0.64 | 589.44 |
| 5 Hz | 782.80 | 91.01 | 38.92 | 0.17 | 652.71 | 960.46 | 652.71 | 625.48 | 529.16 | -1.86 | 621.82 |

## Controller audit

- `flux_target` and `flux_magnitude` are the same quantity: peak per-phase magnetizing flux linkage. The target is derived from line-line RMS V/Hz using `sqrt(2/3)/(2 pi)`, so the former 0.95 versus 1.204 discrepancy was real overflux, not an RMS/peak or line/phase mismatch.
- Stator-resistance compensation now projects the winding-current phasor onto the induced-voltage axis. It adds voltage for motoring active current, subtracts it for generating active current, and does not treat quadrature magnetizing current as a resistive boost.
- Normal target-flux PI regulation is separate from current/overflux/modulation protection. Protection derating starts only near the configured maximum and cannot redefine the displayed target.
- The trace logs base voltage, signed resistance compensation, PI correction, unlimited/final voltage, flux error/integral, every limiter, actual bus frequency, active/reactive power, DC-link behavior, contactors, brake state, and faults at 10 ms intervals.

Observed maxima: 1.152 Wb-turn flux and 2.164 A RMS current.

Conclusion: flux regulation no longer causes the slowdown failure, but the retained scalar source does not establish the requested low electrical frequency in this generating/passive-DC plant. The command reaches its scheduled values while actual bus frequency remains set mainly by rotor motion. Independently initialized machine equilibria exist, but below the present DC-link/chopper operating point the rectifier cannot sustain the required braking load; the capacitor charges, braking torque collapses, and the plant moves away. This is a controller-authority/DC-energy-absorption limit of the present architecture, not proof that a commanded point is stable.

- Final state: `STOPPED`; fault: `NONE`
- Final energy residual: +0.00010724 J
