# Phase 4 extension: dynamic induction generator and capacitors

This extension asks **whether excitation can build from a seed, persist after
inverter disconnection, or collapse**. The application uses it by default.
The `Dynamic flux / capacitor model` checkbox restores the earlier steady-state
model for comparison. These are different machine approximations; the dynamic
model does not use the old peak-torque, peak-slip or reference-V/f parameters.
Those fields are hidden while dynamic mode is selected.

## Try the demonstrations

Select a demonstration in the parameter sidebar, then click **Load demonstration
(resets inputs)** and press **Play**. Each demonstration explicitly sets 240 RPM
initial shaft speed, 100 m starting clearance and 20 kg m² rotational inertia.
The initial spin represents pre-existing motion and contributes initial kinetic
energy. It is not produced for free by the electrical circuit. The mechanical
brake starts released. All other inputs use the dataclass defaults.

| Demonstration | Initial flux seed | Initial capacitor voltage | Exciter |
|---|---:|---:|---|
| Residual seed | 0.005 Wb turn | 0 V | OFF |
| Precharged bank | 0 | 20 V line-RMS-equivalent | OFF |
| Zero seed | 0 | 0 V | OFF |
| Exciter handover | 0 | 0 V | ON; switch OFF after about 1 simulated second |

The spinning residual/precharge examples build voltage with these illustrative
parameters. The zero-seed example remains exactly unexcited: no numerical noise,
artificial minimum flux or growth threshold is injected. At rest, precharge
decays through winding and load losses. A seed does not guarantee excitation;
speed, capacitance, saturation and electrical load determine the outcome.

The initial voltage setting specifies one consistent alpha-beta voltage-vector
snapshot. It does not mean three equal DC voltages around a delta loop. The
initial phase values satisfy Kirchhoff's voltage law. No precharge charger is
modeled; its supplied initial energy is explicitly included in the energy audit.

The initial-flux input is a **decaying stored-flux seed representing residual
magnetism**, not a permanent magnet or a hysteresis/remanence model. It is not
continually replenished. Waiting at rest can let this seed decay before rotation.

## Equations and conventions

Complex quantities represent the two stationary alpha-beta axes, using the
amplitude-invariant Clarke transform. Voltage/current vectors use phase peak
units. Rotor quantities are referred to the stator. Positive shaft speed and
electromagnetic torque correspond to lowering, as in the original mechanics.

```text
psi_s = L_ls i_s + psi_m
psi_r = L_lr i_r + psi_m
i_m = i_s + i_r
i_m = psi_m / L_m0 × (1 + |psi_m|² / psi_sat²)

d(psi_s)/dt = v - R_s i_s
d(psi_r)/dt = -R_r i_r + j pole_pairs omega_mechanical psi_r
T_em = (3/2) pole_pairs Im(conj(psi_s) i_s)

C_equivalent_star = 3 C_delta
C_equivalent_star dv/dt = i_inverter - i_s - v/R_load
I_total = J + m r²
I_total d(omega_mechanical)/dt = m g r + T_em - b omega_mechanical - T_brake
```

Currents are obtained by inverting the flux equations. The nonlinear scalar
relation is monotone, so it has a unique solution. Saturation increases required
magnetizing current with flux instead of imposing an arbitrary voltage ceiling.
No explicit exponential growth/decay envelope, imposed island frequency or
hard-coded self-excitation threshold is used.

The ideal inverter, when ON, supplies whatever current is needed to impose:

```text
v_reference = sqrt(2/3) (V/f) f exp(j 2 pi f t)
dv/dt = j 2 pi f v + (v_reference - v)/tau_excitation
i_inverter = i_s + v/R_load + C_equivalent_star dv/dt
```

This smooth voltage-establishment law avoids resetting charged capacitors on
connection. It has no current/voltage limits, semiconductor switching or losses.
The source's real power now includes charging and machine/load power; it is
no longer restricted to reactive power. That energy is accounted for as external
source energy. This remains an ideal source with explicit turn-on response,
not the later DC-dependent realistic inverter phase.

When the inverter is OFF, **i_inverter=0**. Stator flux, rotor flux and capacitor
voltage are preserved at the switching instant. Subsequent voltage and frequency
follow the circuit equations; the earlier fixed-V/f command no longer imposes
either. Turning ON again uses the ongoing reference oscillator, so a phase
mismatch can cause a transient. There is no synchronizing controller yet.

The former unlimited active-power source/sink is replaced, in dynamic mode,
with a balanced **star-connected AC test resistance**. This is an AC load boundary
for testing excitation, not a rectifier or the Phase 5 DC brake resistor. The
resistance remains connected with the exciter off. A larger resistance means a
lighter load. Generated shaft energy must cover load and winding losses as well
as changes in stored electrical energy.

When capacitance is zero or the bank is disconnected, the bus has no capacitor
state: the enabled ideal inverter imposes its waveform, or the isolated bus
obeys `v=-R_load i_s`. An open machine has zero stator current and torque, while
its rotor field may decay. There is no hidden capacitance floor.

## Parameters

Every physical input remains in `simulation/parameters.py`. New values below are
all **placeholders**, not inferred Liftra or motor specifications.

| Input | Default | Meaning |
|---|---:|---|
| stator_resistance | 0.5 ohm/phase | Stator copper resistance |
| rotor_resistance | 0.4 ohm/phase | Stator-referred rotor copper resistance |
| stator_leakage | 0.01 H/phase | Stator leakage inductance |
| rotor_leakage | 0.01 H/phase | Referred rotor leakage inductance |
| saturation_flux | 1 Wb turn | Flux where magnetizing current is twice the linear value |
| initial_flux | 0.005 Wb turn | Initial stator/rotor flux seed |
| precharge_voltage | 0 V line-RMS-equivalent | Initial capacitor voltage-vector magnitude |
| initial_shaft_rpm | 0 RPM | Initial speed for a normal Reset |
| ac_load_resistance | 100 ohm/phase | Balanced star AC load |
| excitation_response | 0.05 s | Ideal source voltage-establishment time constant |

The existing magnetizing_inductance is now **unsaturated** L_m0. Existing
capacitor_capacitance remains microfarads per **delta branch**. Supply frequency
and V/f set the waveform only while the inverter is enabled. Peak torque is
now a result of circuit parameters, flux and motion, not a manually imposed curve.

Dynamic physical-parameter edits reset the run, as do machine/bank connection
changes. This avoids silently changing stored electrical energy or solving ideal
contactor impulses. **Exciter and brake switches remain live**, preserving the
states needed for the handover experiment. Playback speed and pause also remain
live. Reset reapplies precharge, flux and initial-speed settings, retaining the
switch positions. Normal startup still uses zero shaft speed and the applied
mechanical brake; demonstrations explicitly override these.

## Energy and readouts

```text
P_terminal = 1.5 Re(v conj(i_s))       (positive into machine)
P_inverter = 1.5 Re(v conj(i_inverter)) (positive from external source)
P_load = 1.5 |v|² / R_load
P_copper = 1.5 (R_s |i_s|² + R_r |i_r|²)
W_capacitor = 0.75 C_equivalent_star |v|²
W_magnetic = 0.75 (L_ls |i_s|² + L_lr |i_r|²)
             + 1.5 (|psi_m|²/(2 L_m0) + |psi_m|⁴/(4 L_m0 psi_sat²))

d(W_magnetic + W_capacitor)/dt = P_inverter - P_load - P_copper - T_em omega
```

The displayed energy-balance error compares total magnetic, capacitor, kinetic
and potential energy plus integrated copper/load/mechanical dissipation against
initial energy and signed source input. Impact energy is included in mechanical
dissipation. Frequency/slip during buildup are **instantaneous voltage-vector
estimates**; slip is displayed as undefined near a dead bus. The voltage shown
is `sqrt(3/2)|v|` and current is `|i|/sqrt(2)`: RMS-equivalent magnitudes, not
cycle-window RMS measurements during an unbalanced transient. Reactive powers
use the alpha-beta instantaneous complex-power definition and can briefly have
signs unlike their steady sinusoidal values.

In transients, generated terminal watts need not equal mechanical watts minus
copper loss: the difference can be stored magnetic energy. A slowing rotor after
ground contact and residual electrical voltage are not forced into an algebraic
steady state. The mechanical model itself still applies an inelastic stop at the
ground and holds the load there.

## Integration and validation

The outer mechanics/playback step remains 0.002 s. RK4 electrical substeps are
bounded at 0.0001 s, with smaller substeps for fast circuit/rotation time scales.
Midpoint mechanical speed and averaged electrical torque couple the two models.
Electrical states continue evolving after the load lands. UI work per callback
is bounded; retained simulation-time debt is shown as lag if the requested
playback multiplier exceeds available processing speed.

Tests include nonlinear flux inversion, the circuit energy identity, stationary
precharge decay, zero-seed invariance, insufficient-speed decay, saturation-limited
buildup, handover continuity, disconnected boundaries, mechanics coupling,
timestep refinement, playback independence and ground contact.

With speed externally held at 25 rad/s in a circuit validation test, residual
flux produces approximately 2.84 V at 2 s, 22.09 V at 4 s, 47.03 V at 6 s and
48.41 V at 10 s. This is a fixed-speed test, **not** the accelerating GUI demo.
The normal coupled residual demo reaches about 223.1 V at 5 s because its shaft
accelerates. These are synthetic examples; they do not validate a real motor's
self-excitation threshold or voltage rating.

Model references:

- [Dynamic stationary-frame induction-generator equations](https://www.sciencedirect.com/science/article/pii/S2314717216300642)
- [Standalone self-excited induction generator, saturation and voltage regulation](https://upcommons.upc.edu/bitstream/handle/2117/1273/StandaloneSelfexcited.pdf)

Still excluded: magnetic hysteresis and measured saturation curves, core loss,
spatial harmonics, realistic switching/contactors, capacitor ESR and leakage,
inverter limits/DC bus, rectifier, chopper, bootstrap converter and protection
logic. The provided saturation law is an energy-consistent illustrative law,
not a fit to a particular machine. Review this expanded Phase 4 before Phase 5.
