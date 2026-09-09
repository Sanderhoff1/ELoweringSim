# ELoweringSim - architecture-valid averaged lowering simulator

The default model is a dynamic, energy-conserving representation of the intended
hardware architecture. A finite 24 V battery feeds an averaged boost converter,
a finite auxiliary HV capacitor and a reverse-blocking exciter inverter. The
induction machine feeds an averaged passive rectifier through an explicit
precharge/main-contactor arrangement, followed by the main DC capacitor,
chopper, brake resistor and an optional battery charger.

```text
24 V battery -> boost -> C_aux -> K_EXC / exciter -> AC bus
load -> gear -> induction machine -> AC bus -> diode bridge
AC bus <- K_CAP / capacitor bank
diode bridge -> K_PRECHARGE + R_precharge / K_MAIN -> C_dc
C_dc -> chopper -> resistor
C_dc -> charger -> 24 V battery
```

Run `python -m simulation`, select **Exciter only**, then press **Play**. The
automatic sequence charges the auxiliary link, builds flux with the brake held,
commands brake release and ramps electrical frequency. Throughout startup the
passive bridge can charge the main link through `K_PRECHARGE` and the real series
resistor whenever diode voltage permits. The controller later closes `K_MAIN`,
and the independently connected chopper regulates energy through the resistor.
Select **Automatic 20 -> 10 -> 5 Hz sequence** to run the canonical lowering,
two-step slowdown, brake-apply, and stop profile. The exact speed is not a
hardware prediction.

**Capacitor only** disconnects `K_EXC`. Residual startup releases the brake first
because a stationary induction machine cannot build voltage from residual flux.
The precharged-bank case defines the bank as connected to the machine while the
main rectifier/DC link remains connected through its precharge resistor. Diode
polarity, rather than a startup flag, determines whether power transfers.

The Energy Flow tab shows the complete main path left to right. Connection
labels carry live mechanical, AC and DC transfer quantities. Gold particles
follow signed real power, purple particles oscillate for reactive exchange,
and attached heat/storage branches explain unequal transient powers. Pause
freezes animation. Parameters include battery current limits, resistance,
capacity, boost limits and charger limits.

- [Architecture, control states and model boundary](docs/final-topology.md)
- [Conservation equations and model assumptions](docs/power-model.md)
- [Hidden-switch audit](docs/hidden-switch-audit.md)
- [Scalar V/f controller and automatic sequence](docs/scalar-vf-control.md)
- [Canonical exciter operating-point review](docs/automatic-sequence-exciter.md)
- [Capacitor-only capacitance sweep](docs/capacitor-sweep.md)
- [Canonical capacitor-only natural operating point](docs/automatic-sequence-capacitor.md)
- [300 kg startup sequence, sizing peaks and plot](docs/architecture-demo.md)
- [Component tables at startup, acceleration and steady lowering](docs/power-balance-results.md)
- [Energy Flow preview](energy-preview.png) and [capacitor preview](docs/capacitor-preview.png)
- [Full test output](docs/test-results.txt)

Regenerate tables with `python -m simulation.power_review`, the startup report
with `python -m simulation.architecture_demo`, and previews with
`python -m simulation.preview_energy`. Regenerate the canonical scalar V/f and
capacitor-only traces with `python -m simulation.automatic_sequence`. The previews
render the actual Tk canvas geometry at the normal window size, with the
sidebar's space reserved, and work without an unlocked desktop. If a sandboxed
Python exposes `_tkinter` but hides its Tcl/Tk scripts, preview generation stages
the matching scripts in the ignored `.python/tcl` runtime cache and retries.

Run all tests with `python -m unittest discover -s simulation/tests -v`.
The full dynamic model remains available. A separate conventional equivalent-
circuit calculator supports fast prescribed operating-point sweeps; it does
not replace transient startup or self-excitation dynamics.

## Archived development notes

Everything below describes earlier phases and their former defaults. These
descriptions apply to legacy comparisons, not the reviewed external topology.

### Phases 6–7, chopper and DC-fed excitation

**New: 24 V boost support.** The default **24 V startup** example begins with
an empty DC bus and the brake held. The power-limited boost charges/supports
the shared bus below the chopper threshold, then stands by when generation
takes over. The visual includes battery watts/Wh, support status and boost heat.
See [boost assumptions, equations and startup example](docs/boost-support.md).

The 600 V precharge described below now applies to the **Exciter handover**
comparison, not the default startup. Startup actions are still manual.

**Current default: Phase 7.** The brake chopper has voltage-band control and
finite duty response. The exciter now has current/voltage limits and losses,
and draws from the DC bus. A stated 600 V DC precharge supplies initial energy;
there is no hidden external supply in this mode.

Explore includes a **Phase 5 / 6 / 7** selector, live chopper enable/threshold,
and exciter current-limit controls. The diagram shows the DC feed to the exciter,
duty and limit status, with converter losses in the energy inventory.
See [Phases 6–7 equations, assumptions and validation](docs/phases6-7.md).

The following sections retain the previous phase descriptions. Their ideal
external-exciter assumptions apply to the earlier comparison modes.

**Current phase:** an averaged three-phase diode rectifier feeds a dynamic DC
capacitor and adjustable equivalent brake resistor. The path is visible in
Energy flow, with a live resistance slider in Explore and full energy accounting.
See [Phase 5 equations, assumptions and validation](docs/phase5.md).
The AC voltage bar now shows percent of rated motor voltage, with capacitor
energy separately in joules. Phase 6 now adds chopper control, as described above.

The sections below retain the earlier phase documentation; descriptions of
an AC test load apply when the new rectifier path is disabled.

The UI now uses an **estimated 0.9 kW, four-pole geared hoist, 300 kg load and
200 m height**. The overview includes speed in m/min and a cumulative energy
inventory. See [the example assumptions and energy-bar explanation](docs/small-hoist-example.md).

**Current default: dynamic flux and capacitor voltage.** The simulation can now
build excitation from an initial residual-flux seed or a precharged bank, and
retain or lose excitation after switching the inverter off. Voltage is no longer
forced to zero by that switch. See [the dynamic model guide](docs/dynamic-model.md)
for equations, assumptions, energy accounting, new parameters and validation.

The default **Energy flow** tab shows animated power paths, magnetic-field
brightness, capacitor energy and plain-language feedback about load motion.
Gold arrows show signed real power; purple paths show reactive exchange.
Animation is schematic and freezes on Pause. Bars use illustrative references,
not operating limits. Electrical generation does not necessarily stop acceleration.
The **Parameters** tab holds inputs; **Details & plots** retains the crane and telemetry.

For a quick experiment select **Residual seed**, **Precharged bank**, **Zero seed**
or **Exciter handover** in Explore, then click **Start / restart this example**.
Click the exciter in the diagram to switch it live.
The demos start with a spinning shaft, explicitly included in initial
energy. The handover demo starts with the exciter on; turn it off after about
one simulated second. The dynamic mode uses an explicit AC test load and actual
flux-derived torque, so it is not calibrated to the old illustrative torque curve.

Uncheck **Dynamic flux / capacitor model** for the earlier steady-state model.
The sections below describe that retained baseline. Statements about forced-zero
voltage, zero inverter real power and algebraic compensation apply to that mode
only. Physical parameter edits reset the dynamic mode; exciter/brake switches
remain live. **Phase 5 now replaces that AC test load when enabled.**

Local interactive mechanical simulation of a suspended crane load. **Question:**
How fast does the load descend, and can the mechanical brake hold or stop it,
given mass, effective radius, inertia, damping and brake capacity?

Phase 2 adds a simple induction motor/generator connected to an ideal AC
source/sink. **New question:** Can generator torque limit descent, and how much
mechanical power is returned electrically versus lost in the rotor?
Phase 3 adds ideal V/f excitation and calculated magnetizing demand.
Phase 4 adds parallel AC capacitors. Phase 5 (rectifier, DC bus and equivalent
brake resistance) and later stages remain inactive.

## Phase 4: parallel AC capacitors

**Question:** How much of the modeled excitation demand can capacitors supply,
and how much current does the ideal excitation inverter still need to carry?

The application starts with a capacitor bank connected. Toggle **Connect delta
capacitor bank** to compare immediately with Phase 3. The new physical parameter
`capacitor_capacitance` is **1000 µF per delta branch** by default: three identical
capacitors connected line-to-line across the AC bus. It is a placeholder, not a
component recommendation. The unit is per capacitor, not the sum of the bank.
The model uses only delta connection to keep this phase simple.

Capacitance can be edited live with **Apply inputs live**, without resetting
motion. This represents replacing/switching an ideal bank between steady states;
it does not model a physically variable capacitor, switching surge or contactor.
Reset retains capacitor connection and capacitance.

With `C` in farads per delta branch, `omega_e = 2 pi f`, and RMS voltages:

```text
V_capacitor = V_LL
I_capacitor_branch = omega_e C V_LL
I_capacitor_line = sqrt(3) I_capacitor_branch
Q_capacitor_supply = 3 omega_e C V_LL²
Q_inverter_supply = Q_machine_demand - Q_capacitor_supply
I_inverter_RMS = abs(Q_inverter_supply) / (sqrt(3) V_LL)
S_inverter = abs(Q_inverter_supply)
P_capacitors = P_inverter = 0
C_full_compensation = 1 / (3 omega_e² L_m)
```

Positive inverter VAR means it supplies the shortfall. Negative inverter VAR
means it **absorbs** excess capacitive reactive power. Current magnitude and
apparent power remain nonnegative. Surplus compensation is not clipped, and
the ideal inverter holds the configured voltage regardless of bank size.
The schematic's inverter VAR arrow reverses when compensation exceeds demand.
Capacitor/inverter supplies use positive-delivery signs; machine demand uses
positive-absorption signs. Their balance is `Q_cap + Q_inv = Q_machine`.

At default **5 Hz, 40 V line-line, Lm=0.2 H**:

| Case | Capacitor supply | Inverter VAR | Inverter current |
|---|---:|---:|---:|
| Bank disconnected | 0 VAR | +254.65 VAR | 3.676 A |
| 1000 µF per delta branch | 150.80 VAR | +103.85 VAR | 1.499 A |
| About 1688.69 µF per delta branch | 254.65 VAR | About 0 VAR | About 0 A |
| 2000 µF per delta branch | 301.59 VAR | -46.95 VAR | 0.678 A |

The inverter still establishes voltage/frequency at full compensation even
though its modeled steady reactive current is zero. **Capacitors do not increase
generator braking torque in this fixed-voltage model.** Machine magnetizing
current, torque, real generated power and rotor heat are unchanged: only the
reactive-current contribution of the inverter is reduced. Thus this phase does
not make it easier to catch a load that is already beyond the useful torque-slip
region. With fixed V/f, capacitor VAR grows as `f³`, whereas the modeled machine
magnetizing VAR grows as `f`; a fixed bank can overcompensate at higher frequency.

**Boundary:** all quantities are balanced sinusoidal steady-state values. This
phase does not model capacitor voltage/charge states, residual voltage, losses,
switching inrush, resonance, harmonic currents, magnetic saturation or autonomous
self-excitation. When the inverter is disabled, the existing model sets AC
voltage and torque to zero even with the bank connected. That is a modeling
boundary, not a prediction that a real induction generator cannot self-excite.
The displayed full-compensation capacitance is a reactive-balance calculation,
not a voltage-stability criterion. Real startup and capacitor-only operation
would require a dynamic flux/voltage model.

Reference for shunt compensation and reactive-power signs:
[Schneider Electric Electrical Installation Guide](https://www.electrical-installation.org/enwiki/Reactive_power_of_capacitors).
Tests cover delta voltage/current factors, zero/full/excess compensation,
frequency and voltage scaling, unchanged mechanics/real power, explicit
inverter-off behavior, input validation and playback independence.

## Phase 3: ideal active excitation (baseline with capacitor bank disconnected)

**Question:** How much excitation current and reactive power does the assumed
magnetizing branch require, and how does changing V/f affect generator torque?

The application now starts with the machine connected and the ideal excitation
inverter enabled. **Enable ideal excitation inverter** switches excitation live.
Turning it off immediately removes voltage, electromagnetic torque and electrical
power. Residual flux and self-excitation are not modeled. Disconnecting the machine
also removes these quantities. Reset retains both switches.

The ideal inverter sets balanced AC voltage at a fixed frequency setpoint and
supplies exactly the modeled magnetizing VAR demand. The Phase 2 ideal real-power
source/sink remains as a separate boundary, providing motoring watts or absorbing
generated watts. It supplies no reactive power in Phase 3. This is an explicit
ideal P/Q split, not yet a physical inverter/DC-bus circuit. A Q-only inverter
alone cannot provide starting real power or absorb generated energy.

New parameters (all illustrative **placeholders**, in `parameters.py`):

| Parameter | Unit | Default | Physical meaning |
|---|---|---:|---|
| volts_per_hz | V/Hz | 8 | Commanded line-line RMS voltage per Hz |
| reference_volts_per_hz | V/Hz | 8 | Reference V/f for the existing peak torque |
| magnetizing_inductance | H/phase | 0.2 | Linear star-equivalent phase inductance |

```text
V_LL = (volts_per_hz) f
V_phase = V_LL / sqrt(3)
X_m = 2 pi f L_m
I_excitation = V_phase / X_m           (RMS, star-equivalent line current)
Q_machine = 3 V_phase I_excitation    (positive inductive VAR demand)
Q_inverter_supply = Q_machine
P_inverter = 0                       (ideal, lossless Q-only branch)
S_inverter = Q_machine
flux_ratio = volts_per_hz / reference_volts_per_hz
T_peak_effective = peak_motor_torque × flux_ratio²
I_active = P_electrical_input / (sqrt(3) V_LL)
I_machine = sqrt(I_active² + I_excitation²)
S_machine = sqrt(P_electrical_input² + Q_machine²)
```

The effective peak torque replaces the Phase 2 curve's peak in the existing
Kloss equation. All torque and electrical quantities become zero without
excitation. At the reference V/f, the mechanical trajectory exactly reproduces
Phase 2. At fixed frequency, halving V/f halves excitation current and quarters
both reactive demand and peak torque. At constant V/f, changing frequency scales
voltage and VAR proportionally while magnetizing current stays constant.

The supply is fixed-frequency between user edits, with instantaneous V/f updates;
there is no speed-feedback controller, voltage cap, field-weakening region,
switching, current limit, inverter loss, flux transient or DC-bus dependence.
The torque curve's peak-slip parameter remains fixed as a phenomenological
simplification. No rotor-resistance/frequency scaling is claimed.

**Scope of excitation demand:** only the linear magnetizing branch is counted.
Rotor/stator leakage VAR and saturation are omitted; the separate phenomenological
torque curve is retained. Thus inverter current is a magnetizing-demand estimate,
not a hardware sizing result or a full equivalent-circuit prediction. Machine
current adds the modeled active component and is likewise approximate.
Reactive VAR is not real energy consumed: the ideal inverter's average watts
are zero, even though its current and apparent power are nonzero.
For the distinction between magnetizing inductance, winding connection and
full motor models, see the
[MathWorks simplified induction motor reference](https://www.mathworks.com/help/sps/ref/simplifiedinductionmotor.html).

At the default 5 Hz and 8 V/Hz: **40 V line-line RMS**, **3.676 A excitation**,
and **254.65 VAR** supplied by the inverter. These remain constant with speed in
the linear magnetizing approximation, including at synchronous speed when real
power is zero. Real generation and rotor losses are still calculated separately.
Tests verify these analytical relationships, power balance, loss of excitation,
V/f torque scaling, Phase 2 trajectory equivalence and playback independence.

Run from this directory with Python 3.10+ including Tkinter (no pip packages):

```powershell
python -m simulation.main
python -m unittest discover -s simulation/tests -v
```

This workspace also has a local Python runtime installed for validation:

```powershell
.\.python\python.exe -m simulation.main
.\.python\python.exe -m unittest discover -s simulation/tests -v
```

The local runtime and installer are ignored by Git.

In VS Code select your Python interpreter, then run the first command in its
terminal. If Windows provides `py` rather than `python`, use `py` instead.
The app starts paused with the brake applied and the ideal AC source connected.
Uncheck **Connect machine to AC bus** to reproduce Phase 1.
The top toolbar always contains
Play/Pause, Reset, playback speed and Release brake. Both the parameter sidebar
and the main view have scrollbars; the mouse wheel scrolls the pane under the
pointer (Shift+wheel scrolls the main view horizontally). The window initially
fits the screen and can shrink to 720×480. Drag the divider to resize the panes.
Press Play, then enable brake release to lower the load. Uncheck release to apply the brake. Inputs apply
together when you click **Apply inputs live**. Invalid inputs leave the current
model unchanged. Reset clears time, travel, rotation and history while retaining
the selected parameters, AC connection, brake state and playback state.

Mass, radius, inertia and crane-height edits reset the run: changing these during motion
would require additional momentum/geometry physics. Gravity, damping and brake
capacity, brake response and motor curve/supply parameters can change live.
Frequency edits change the ideal field speed instantly; no frequency ramp is
implemented, and voltage follows the V/f setting. Pole-count edits substitute another assumed motor
curve and should be followed by Reset for a clean comparison.
Changes represent externally imposed conditions;
energy comparisons across changes in gravity are not conservation tests.

## Assumptions and equations

Downward load travel `x`, downward velocity `v`, and shaft rotation `theta` /
`omega` are positive. Starting travel and angle are zero. A taut, massless rope
and rigid, lossless transmission give `x = r theta`, `v = r omega`.
Effective radius `r = drum radius / (shaft speed / drum speed)` incorporates
gearing. Inertia `J` includes rotating
parts reflected to the shaft but **excludes** the suspended mass.

```text
I = J + m r²
gravity torque = m g r
I d(omega)/dt = m g r + T_em - b omega - T_brake
a = r d(omega)/dt
RPM = omega × 60 / (2 pi)
U = -m g x                      (potential relative to starting height)
K = 0.5 I omega²
P_gravity = m g v               (mechanical power entering from gravity)
P_viscous = b omega²
P_brake = B |omega|             (using actual engagement, including release decay)
```

Applied brake torque opposes motion with magnitude `B = brake_torque × q`, where
`q` is the brake engagement fraction. It follows `dq/dt = (command - q)/tau`,
with command 1 for apply and 0 for release. The configurable `brake_response`
is `tau`: engagement moves 63.2% toward its command in one time constant and
95% in three. The default 0.3 s is an illustrative placeholder, not measured
brake performance. Setting it to zero recovers the instantaneous brake.
Reset initializes the brake at its selected command. At rest it
balances the combined gravity and electromagnetic torque up to its capacity;
the load stays stationary if `B >= m g r + T_em(0)`.
After release, capacity decays toward zero. Static and sliding capacity are equal.
At fixed parameters, `d(K+U)/dt = T_em omega - P_brake - P_viscous`.

Each 0.002-second physics step integrates the actuator response analytically,
then uses its midpoint capacity for the mechanical equation. That constant-torque
substep is integrated analytically, splitting at a stop so the brake cannot cause
false reversal. Electromagnetic torque is evaluated at a predicted half-step
speed, then frozen for the full mechanical substep. Dynamic-brake and motor
motion are timestep approximations; timestep-refinement tests cover the demo
parameters. Extreme inertia/torque combinations may need a smaller physics step;
parameter input bounds are not a numerical accuracy guarantee.
The configurable crane height is the initial clearance under the load. Ground
contact is located within the step by bisection, and then travel is fixed at
the height, shaft speed is set to zero, and the ground supports the load. Impact
speed, time and removed kinetic energy are recorded. This is a perfectly
inelastic rigid stop of the equivalent mechanism: it does not predict peak
force, rope slack, rebound or structural damage. Reset starts a new descent.
The source remains connected after landing: the stopped motor still draws power
and produces rotor heat in this model. Disconnect it explicitly to remove this
power. There is no automatic contactor or protection logic yet.
The UI accumulates wall time multiplied by playback speed and consumes fixed
steps independently of rendering. 0.05× takes 20 real seconds per simulated
second; 10× takes 0.1 real seconds. Rendering is targeted at roughly 60 FPS.
Work per frame is capped at 2,000 steps; any backlog is retained rather than
skipping physics. An overloaded machine may lag behind requested playback.
The shaft marker is a sampled orientation and can visually alias at high RPM;
use slow playback and the numerical RPM readout.

## Physical inputs

All physical parameters and their units, defaults, meanings, status and allowed
input ranges live in `simulation/parameters.py`. Input bounds are numerical UI
guardrails, not equipment ratings. No equipment specifications are known yet.

| Name | Unit | Default | Meaning | Status |
|---|---|---:|---|---|
| mass | kg | 100 | Suspended mass | Placeholder |
| radius | m/rad | 0.1 | Load travel per shaft radian | Placeholder |
| inertia | kg m² | 1 | Reflected rotational inertia excluding load | Placeholder |
| damping | N m s/rad | 0.2 | Viscous shaft friction | Placeholder |
| brake_torque | N m | 150 | Applied brake capacity at shaft | Placeholder |
| brake_response | s | 0.3 | Application/release time constant | Placeholder |
| crane_height | m | 10 | Initial load clearance / downward travel limit | Placeholder |
| gravity | m/s² | 9.81 | Constant local gravity approximation | Estimated |
| supply_frequency | Hz | 5 | Ideal field frequency in lowering direction | Placeholder |
| pole_pairs | pairs | 2 | Integer pole-pair count (four poles) | Placeholder |
| peak_motor_torque | N m | 120 | Peak assumed motor/generator torque | Placeholder |
| peak_slip | 1 | 0.2 | Slip magnitude at peak torque | Placeholder |

Please replace placeholders with your crane's mass, drum radius and gear ratio,
reflected inertia, friction estimate, and shaft-referred brake torque during
review. With AC connected, the initial brake holds because 150 N m exceeds
98.1 N m gravity torque plus 46.154 N m motor starting torque.
The 5 Hz default is deliberately chosen to demonstrate generation within the
10 m travel; it is not a rated motor frequency. Phase 3 adds the explicit V/f setting.

## Phase 2 induction approximation (retained inside Phase 3)

The ideal source represents a balanced three-phase supply that establishes
excitation immediately and can supply or absorb unlimited active power.
Rotation of the field is always in the lowering direction. A symmetric Kloss
approximation gives a finite torque peak and declining torque at large slip:

```text
omega_sync = 2 pi f / pole_pairs
slip = (omega_sync - omega) / omega_sync
z = slip / peak_slip
T_em = 2 peak_motor_torque z / (1 + z²)
P_electrical_input = T_em omega_sync
P_motor_shaft = T_em omega
P_rotor_loss = T_em (omega_sync - omega) >= 0
P_AC_export = -P_electrical_input
P_electrical_input = P_motor_shaft + P_rotor_loss
```

Positive torque drives lowering. Below synchronous speed, the motor can help
accelerate the load and draws power. Above synchronous speed, slip and torque
are negative: the generator opposes descent and exports power. At synchronism
torque and active power are zero. Phase 3 explicitly calculates magnetizing
reactive power as described above. Disconnection
sets torque and all electrical powers to zero; displayed slip then only compares
shaft speed to the configured hypothetical source speed.

The torque curve is parameterized directly, so no realistic-looking winding
resistances or inductances have been invented. Stator resistance, core loss and
flux transients are neglected. Rotor copper loss follows the steady-state power
balance. In Phase 3, voltage follows V/f and torque is scaled by the squared V/f
ratio relative to its reference. This model is suitable for qualitative
descent/generation studies, not thermal or nameplate-performance predictions.

Reference for induction-machine slip, generator operation and power balance:
[MIT induction-machine notes](https://web.mit.edu/6.11s/2005/notes/pdfs/chapter6.pdf).
The torque-curve simplification is discussed in
[this equivalent-circuit/Kloss study](https://www.mdpi.com/2075-1702/9/12/340).

## Validation cases

Tests compare simulated states to analytical results, including playback/FPS
independence, viscous motion, release/reapplication and input validation.
The four core cases use `m=100 kg`, `r=0.1 m/rad`, `J=0`, `b=0`, `g=9.81 m/s²`,
instantaneous brake response, AC disconnected, and a 100 m height so the ground does not intervene:

| Case | Analytical result |
|---|---|
| Free fall, B=0, initially at rest | At 1 s: x=4.905 m, v=9.81 m/s |
| Hold, B=150 N m | x=v=a=0 |
| Partial brake, B=49.05 N m | At 1 s: x=2.4525 m, v=4.905 m/s |
| Stop, B=150 N m, initial v=2 m/s | a=-5.19 m/s² until stop; distance=0.385356455 m; then held |

Setting `J=0` is essential for true free fall: positive rotational inertia
reduces acceleration to `g / (1 + J/(m r²))` when friction and brake are absent.

Phase 2 tests check torque signs/peaks, zero torque at synchronous speed, positive
rotor losses, power balance, disconnection, static brake loading, landing,
playback independence and timestep refinement. An analytical equilibrium check
sets damping and brake torque to zero with ample travel. For load torque `L`
below `T_peak`, the stable generating branch is
`z = L / (T_peak + sqrt(T_peak²-L²))` and
`omega_eq = omega_sync (1 + peak_slip z)`.
The simulated final speed and torque agree to eight decimal places.

With the normal UI defaults, start with Play and Release brake. At t=3 s the
model gives approximately 1.724 m/s, 164.65 RPM, -9.77% slip, -94.64 N m motor
torque, 1,486.7 W AC export and 145.2 W rotor loss. The load is about 4.666 m below
its start. These are illustrative simulation results, not equipment predictions.

## Limits and review boundary

There is no contact-force model, elasticity, backlash, rope slip,
gear loss, brake thermal fade, dynamic electromagnetic/flux model, full equivalent
circuit, realistic excitation inverter, dynamic capacitor model, DC bus, bootstrap or protection
control. There is no guarantee of a steady generating speed if the available
generator torque and friction cannot balance gravity. The crane scene uses a
project-local technical illustration informed by the Liftra LT1200 arrangement:
a compact crane mounted through an interface/base in the opened nacelle. It is
a generic illustration, not a certified dimensional drawing or a Liftra asset.
The cable, hook, load, sheave marker and height ruler are live overlays driven
by the simulation. The view uses the fixed configured height and shows a landing
level. History retains 75
simulated seconds sampled every 0.05 s, with separate plot scales. Potential
energy is relative and becomes negative below the starting position.

This is an illustrative model, not an equipment safety assessment. Review the
mechanics, capacitor compensation, defaults and UI before authorizing Phase 5.
