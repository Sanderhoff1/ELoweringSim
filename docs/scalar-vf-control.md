# Scalar V/f emergency-lowering control

This is a scalar V/f controller for the reviewed induction-machine plant. It
is deliberately not field-oriented control: there is no d/q current loop,
rotor-flux angle estimator, field-weakening scheduler, or torque-current
regulator.

## Command and limits

The controller ramps an electrical-frequency command and requests line-line RMS
voltage. The base-flux expression and measured flux are both **peak per-phase
magnetizing flux linkage**, in Wb-turn:

```text
Vbase_LL = sqrt(3/2) 2 pi f* psi_base
V*_LL = max(0, Vbase_LL + Delta V_Rs + Delta V_PI) k_protection
psi_base = min(psi_exciter, sqrt(2/3) (V/Hz) / (2 pi))
Delta V_Rs = sqrt(3/2) R_s projection(I_phase, j psi/|psi|)
```

The resistance term uses the winding-current **phasor**, not current magnitude.
Its sign follows real current on the induced-voltage axis: positive for motoring,
negative for generating, and zero for ideal quadrature magnetizing current. This
matters because the old magnitude-only `sqrt(3) R_s I_rms` term always increased
voltage, including during generation.

`Delta V_PI` is a bounded PI correction around `psi_base`. This normal regulator
is distinct from `k_protection`, which derates excitation only when measured
motor RMS current exceeds 95% of its limit or magnetizing flux enters the upper
protection region at 95% of its maximum. The target remains visible and unchanged
when protection acts. The requested voltage is also limited by the actual
auxiliary-link voltage. The existing
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
and a JSON summary under `docs/`. For the five-point independent initialization
and high-resolution transition audit, run:

```powershell
python -m simulation.scalar_vf_validation
```

It writes `scalar-vf-steady-points.csv/.md` and a 10 ms
`scalar-vf-transition.csv/.md` trace under `docs/`.

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

The trace exposes sequence state, command/target/**actual bus** frequency, speed and RPM,
synchronous RPM and slip, line voltage, machine active/reactive current, current
limit, flux/target/maximum, V/f base voltage, signed resistance compensation,
PI correction, unlimited/final voltage, flux error/integral, torque and shaft power, copper/core/magnetic-storage
power, capacitor current/VARs, exported and rectified power, DC-link voltage and
capacitor power, chopper duty/resistor power, brake command/state/capacity,
battery/boost/auxiliary quantities, contactor states, limit classifications,
fault/runaway state, and the energy residual.

## Interpretation of low-frequency results

A frequency command is not evidence that the islanded generating bus reached
that frequency. The report classifies a point as `frequency-control-limited`
when actual bus frequency differs by more than 0.5 Hz or 5% from the command.
With the present parameters, independent nonlinear machine/load calculations
find target-flux torque equilibria at 20, 15, 10, 7.5, and 5 Hz. They are not
stable equilibria of the complete present plant: their rectified voltages are
below the 500 V chopper threshold, so the DC capacitor cannot sustain continuous
resistor loading. As it charges, generating torque collapses and rotor speed and
bus frequency move away from the command. Lower-frequency theoretical points
also require larger negative slip and lose a greater fraction of mechanical
input in rotor/stator copper.

Accordingly, this audit fixes a controller-caused overflux mechanism but does
not claim that scalar V/f alone makes 20→10→5 Hz physically viable. Resolving
the remaining limitation would require greater electrical frequency/torque
authority or DC-side energy absorption; neither topology nor control family is
redesigned here.

This remains a simulation model, not deployable safety firmware. The parameters
are placeholders, the chopper and converters are averaged, and the runaway
detector is a transparent diagnostic rather than certified overspeed protection.
