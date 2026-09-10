# Scalar V/f 20 → 15 → 10 → 7.5 → 5 Hz transition

The companion CSV is sampled every 10 ms. It contains the requested command decomposition, flux error/integral, current/flux/voltage limit flags, actual bus frequency, active/reactive power, DC link, chopper, contactor, brake, controller-state, and fault telemetry. Targets below are command-settled samples; they are not called physical operating points unless actual bus frequency also follows.

| Command [Hz] | Actual bus [Hz] | Flux target / actual / max [Wb] | V base / Rs / PI / final [V LL RMS] | I [A RMS] | AC export / DC in / resistor [W] | Limit flags (I/F/V) | State / fault |
|---:|---:|---:|---:|---:|---:|---|---|
| 20 | 45.18 | 0.950 / 1.067 / 1.300 | 146.0 / -10.9 / -35.5 / 99.6 | 1.80 | 469.8 / 453.4 / 302.7 | 0/0/0 | LOWERING / NONE |
| 15 | 52.30 | 0.950 / 0.951 / 1.300 | 109.4 / -12.4 / -47.4 / 49.7 | 1.67 | 579.7 / 557.1 / 552.8 | 0/0/0 | LOWERING / NONE |
| 10 | 54.36 | 0.950 / 0.921 / 1.300 | 72.9 / -13.1 / -32.4 / 27.4 | 1.67 | 621.9 / 596.7 / 594.7 | 0/0/0 | LOWERING / NONE |
| 7.5 | 54.36 | 0.950 / 0.922 / 1.300 | 54.6 / -13.2 / -21.7 / 19.7 | 1.67 | 625.3 / 599.9 / 599.2 | 0/0/0 | LOWERING / NONE |
| 5 | 54.73 | 0.950 / 0.919 / 1.300 | 36.6 / -13.6 / -8.9 / 14.0 | 1.70 | 648.1 / 621.1 / 617.3 | 0/0/0 | LOWERING / NONE |

Maximum recorded flux/current: 1.152 Wb-turn / 2.164 A RMS. Final state: `STOPPED`; fault: `NONE`.

Interpretation: compare the actual-bus and command columns before judging a target viable. In the retained architecture the flux loop can remain controlled while the generating rotor and passive rectifier/DC load determine a much higher actual electrical frequency. That is a plant/control-authority limitation, not a hidden relabeling of command frequency.
