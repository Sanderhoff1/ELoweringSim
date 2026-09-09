# Scalar V/f emergency-lowering control

This is a scalar V/f controller for the reviewed induction-machine plant. It
is deliberately not field-oriented control: there is no d/q current loop,
rotor-flux angle estimator, field-weakening scheduler, or torque-current
regulator.

## Command and limits

The controller ramps electrical frequency, then requests line-line RMS voltage

```text
V*_LL = (V/Hz) f* k_limit + sqrt(3) R_s I_s
psi*  = psi_base k_limit
psi_base = min(psi_exciter, sqrt(2/3) (V/Hz) / (2 pi))
```

The second term is measured stator-resistance compensation, not a fixed voltage
boost. `k_limit` is reduced when measured motor RMS current exceeds 95% of its
limit or estimated magnetizing flux exceeds 90% of its maximum. The requested
voltage is also limited by the actual auxiliary-link voltage. The existing
converter/network solve still enforces inverter current, positive active-power,
reverse-power blocking, modulation, battery, boost, and DC-link constraints;
readouts are never cosmetically clipped.

Default illustrative settings are 15 Hz/s acceleration, 3 Hz/s deceleration,
5 Hz minimum controlled frequency, 6 A RMS machine-current limit, 0.95 Wb-turn
flux target, and 1.30 Wb-turn maximum flux. All are editable `Parameters` fields
and must be replaced with motor/converter data before design use.

## Automatic sequence

The exciter sequence is:

```text
OFF
 -> AUXILIARY_START       boost charges C_aux; brake applied; K_EXC open
 -> EXCITATION_BUILD      K_EXC closed; 5 Hz scalar V/f; brake applied
 -> READY_TO_RELEASE      flux/current dwell passed; brake still applied
 -> BRAKE_RELEASE         release command; wait for physical feedback
 -> LOWERING              ramp/hold at 20 Hz
 -> SLOWDOWN_1            ramp/hold at 10 Hz
 -> SLOWDOWN_2            ramp/hold at 5 Hz
 -> BRAKE_APPLY           command brake while 5 Hz excitation remains
 -> STOPPED               physical brake applied and speed low; remove excitation
```

Emergency stop, auxiliary/main DC overvoltage, gross overflux, sustained machine
overcurrent, or a persistent runaway diagnostic transitions to `FAULT` and commands the brake applied. Brake
command and brake physical state remain separate telemetry.

The Explore tab checkbox **Automatic 20 -> 10 -> 5 Hz sequence** selects this
profile. It is honored by live simulation and by pre-simulation/replay. The
same deterministic profile is available without UI interaction through:

```powershell
python -m simulation.automatic_sequence
```

That command writes CSV traces, an SVG plot, Markdown operating-point reviews,
and a JSON summary under `docs/`.

Run `python -m simulation.capacitor_sweep` to regenerate the passive capacitance
sensitivity table. The sweep changes capacitance only; it never commands bus
frequency or voltage.

## Capacitor-only boundary

Capacitor-only mode shares the plant, switchgear, brake sequencing, telemetry,
and fault handling. It does **not** run scalar V/f and receives no 20/10/5 Hz
command. Its bus voltage and frequency emerge from rotor speed, residual or
precharged initial energy, machine parameters, capacitance, saturation, losses,
rectifier/DC loading, and the mechanical trajectory. The canonical report
therefore gives its natural operating point and labels the frequency command
not applicable.

## Telemetry used for review

The trace exposes sequence state, command/target/bus frequency, speed and RPM,
synchronous RPM and slip, line voltage, machine active/reactive current, current
limit, flux/target/maximum, torque and shaft power, copper/core/magnetic-storage
power, capacitor current/VARs, exported and rectified power, DC-link voltage and
capacitor power, chopper duty/resistor power, brake command/state/capacity,
battery/boost/auxiliary quantities, contactor states, limit classifications,
fault/runaway state, and the energy residual.

This remains a simulation model, not deployable safety firmware. The parameters
are placeholders, the chopper and converters are averaged, and the runaway
detector is a transparent diagnostic rather than certified overspeed protection.
