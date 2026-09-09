# Instantaneous and accumulated conservation

The running topology is `ExternalLoweringModel` (the historical class name is
retained for compatibility). This review started from current HEAD
`ba04d142871a721a76d8af62ba0a07807e64a667`.
The model's only energy inputs are finite battery energy, explicit initial stored
energy and decreasing load height. `external_supply_voltage` is a legacy
parameter and cannot supply this model.

Each entry in `readings()['power_diagnostics']['components']` exposes `input`,
`output`, `heat`, `storage_rate`, `energy`, and an independently evaluated
`residual = input - output - heat - storage_rate`. Connections expose signed
power and actual terminal voltage/current; AC connections also expose P, Q,
active/reactive current components, and RMS current. The bridge current is a
fundamental equivalent, not switching-waveform RMS. The UI consumes these
entries directly. Its only conversions are formatting, units and drawing.

## Component equations

All P quantities below are signed. Positive shaft power enters the generator;
positive machine AC power leaves it. Battery current is positive on discharge.
For peak alpha-beta phasors, `S = 3/2 v conjugate(i) = P + jQ`.

| Component | P_in | P_out | P_heat | dE_stored/dt |
|---|---|---|---|---|
| Load / gravity | 0 | mg u | 0 | -mg u (height energy) |
| Gear / bearings / mechanics | mg u | -T_em omega | T_gear abs(omega) + T_bearing abs(omega) + T_brake abs(omega) + b omega² | J_total omega alpha |
| Induction machine | -T_em omega | -Re(S_machine) | stator copper + rotor copper + core | magnetic derivative below |
| AC bus | P_machine + P_exciter | P_rectifier + P_capacitor | 0 | 0 |
| Capacitor bank | P_capacitor | 0 | 0 | 3/2 C_ac Re(conj(v) dv/dt) |
| Rectifier / source impedance | P_ac | V_dc I_rect + P_precharge | P_bridge_loss | 0 |
| Main-link precharge resistor | V_dc I_rect + P_precharge | V_dc I_rect | P_precharge | 0 |
| DC link | V_dc I_rect | P_chopper + P_charger | 0 | C_dc V_dc dV_dc/dt |
| Ideal averaged chopper | duty V_dc²/R_brake | same | 0 | 0 |
| Brake resistor | duty V_dc²/R_brake | 0 | same | 0 |
| Exciter | P_aux,out | Re(S_exciter) | 3/2 R_conduction abs(i_exciter)² + idle | 0 |
| Auxiliary HV link | P_boost,out | P_aux,out | 0 | C_aux V_aux dV_aux/dt |
| Boost | P_battery,to_boost | efficiency times input | input minus output | 0 |
| Charger | P_dc,to_charger | efficiency times input | input minus output | 0 |
| Battery | P_charger,out | P_boost,in | R_battery I_battery² | -V_oc I_battery |

`J_total = J_shaft + m r²`; it includes the translating load and rotor/shaft.
Ground contact converts the remaining kinetic energy to explicitly accumulated
impact heat. The mechanics integrate to the contact time before changing speed.
The mechanical brake and damping heat are included at their actual torques.

Magnetic storage is the sum of leakage energies and the nonlinear magnetizing
energy integral:

```
E_mag = 3/4 (L_ls |i_s|² + L_lr |i_r|²)
      + 3/2 (|psi_m|²/(2 L_m) + |psi_m|⁴/(4 L_m psi_sat²))
dE_mag/dt = 3/2 Re(conj(i_s) dpsi_s/dt + conj(i_r) dpsi_r/dt)
E_ac = 3/4 C_ac |v|², C_ac = 3 C_delta
E_aux = 1/2 C_aux V_aux²
E_dc = 1/2 C_dc V_dc²
```

The magnetic derivative is evaluated from the winding state derivatives, not
created by subtracting displayed power readings. Tests also check it against a
finite difference of the energy function. Capacitor Q describes exchange with
the field and never enters a real-power or accumulated-energy residual.

## Exciter-only constraint and voltage capability

There is no AC capacitor state in exciter mode. A scalar V/f controller ramps
frequency and requests line-RMS voltage from the configured V/Hz slope plus
measured `sqrt(3) R_s I_s` compensation. Flux and motor-current feedback derate
the requested voltage and flux target before the network solve. It is not FOC
and has no d/q torque-current loop or shaft-speed estimator.

Every integration stage solves the two real equations
`i_exciter = i_stator + v/R_core + i_rectifier` for terminal voltage.
The current evaluator applies total RMS current, reactive-component current,
nonnegative AC active current, state-dependent active-power, auxiliary-energy,
and modulation-capability limits *inside* that solve.
Terminal voltage is not integrated from an unlimited requested derivative.
Generated real power therefore cannot enter the exciter. The field-building
active-power limit permits magnetic buildup and loss supply; the lower run limit
prevents intentional material motoring after brake release.

The common solve path uses bounded continuation/Newton steps. Multiple physical
seeds and a bounded derivative-free fallback handle clipped limit boundaries.
A recognized no-conducting-equilibrium limit condition is reported as
`PHYSICALLY_INFEASIBLE_BLOCKED`; an unresolved numerical failure raises
`ExciterSolverError` instead of being silently interpreted as converter behavior.

The balanced inverter's linear modulation ceiling is
`abs(v + R_virtual i_exciter) <= V_aux / sqrt(3)`. The normal example uses a
600 V auxiliary-link target; 520 V did not provide linear modulation headroom
for the normal field plus winding/output voltage drops. This auxiliary output
is separate from the approximately 524 V brake DC link. Its current ceiling is
`P_boost,out / V_boost <= boost_output_current_limit`.

The charger converter's specified operating range begins at 480 V in the normal
example. Below that input voltage its controller cannot operate; at or above it,
SOC, current, power and efficiency limits determine its draw. Battery limitations
can still prevent startup; the controller does not manufacture missing real power.

## Battery, boost and charger

The battery is a finite, constant-open-circuit-voltage energy store with series
resistance: `V_t = V_oc - R I`, `P_terminal = V_t I`.
The low-current root of this equation determines signed current, including
simultaneous boost demand and charger output. Thus terminal voltage rises on
charge and falls on discharge; internal heat is always nonnegative.

Boost input is bounded by discharge current, the battery's maximum-power point,
remaining chemical energy over the integration step, converter input power,
efficiency, and high-voltage output current. Limiting occurs before electrical
integration. The high-side current command has finite response. Its midpoint
power charges `C_aux`; inverter DC input discharges it. A bounded discrete-energy
solve handles startup from exactly zero volts without a hidden source.
The charger limits *net battery charge current* and chemical
headroom, while allowing simultaneous boost use. SOC is not clipped after
integration to hide missing energy.

## Reset, integration and limitations

Capacitor-bank precharge is an explicit initialization transfer with `K_CAP`
already connecting the bank to the machine. The main rectifier path is connected
through `K_PRECHARGE` and `R_precharge` when the main DC path is enabled.
AC energy is `1/2 C_ac V_LL²`, bounded by finite battery energy and boost voltage
capability. Battery removal is `E_ac / precharge_efficiency`; the difference is
accumulated initialization heat. No incompatible charged capacitors are switched
together at reset.

Main DC-link precharge is dynamic. Enabling the main DC path commands the real
`K_PRECHARGE` contactor immediately; it is not conditional on terminal power,
AC voltage, motor rating, brake release or any readiness flag. `R_precharge`
limits physical charging of `C_dc`. Diode polarity decides whether current flows.
`K_MAIN` is a real contactor that bypasses the resistor when commanded, normally
after the measured DC voltage matches the available rectified crest. Bridge/source
loss and precharge-resistor loss are distinct accumulated sinks. The chopper is
connected across `C_dc` and is not gated by `K_MAIN`.

The accumulated residual is current height + kinetic + magnetic + AC capacitor
+ auxiliary capacitor + main DC capacitor + battery energy, minus initial
inventory, plus every accumulated heat term (including battery I²R, both
precharge losses and impact). No Q appears in it.
RK steps reject/subdivide when their AC/magnetic energy change disagrees with
integrated physical work. This resolves stiff winding decay after converter
blocking; it does not correct the state energy cosmetically.

This remains a balanced, averaged fundamental model. It does not resolve diode
harmonics, switching ripple, battery electrochemistry, or individual cell
voltages. `Pac - Pdc` is **rectifier/source loss**, because the configured
resistance includes source impedance as well as the bridge.

Run `python -m simulation.power_review` for component tables at reset, startup,
acceleration and steady lowering. Run `python -m simulation.architecture_demo`
for the full sequence, sizing peaks, CSV and SVG plot. Run
`python -m simulation.preview_energy` for previews rendered from the actual Tk
canvas geometry at the normal application size with its sidebar present.
The reviewed 20 -> 10 -> 5 Hz sequence and passive-capacitance sweep are
regenerated with `python -m simulation.automatic_sequence` and
`python -m simulation.capacitor_sweep`; see [scalar-vf-control.md](scalar-vf-control.md).


## Startup support and live controls

In **Capacitor only**, **Battery excitation** is a supported start condition.
It runs the finite battery/boost/exciter path while building the field and
maintaining AC-bank excitation. Once flux exceeds the configured startup
threshold for the configured dwell, support disconnects and stays disconnected
until Reset. This is distinct from **Precharged capacitor bank**, which remains
a one-time initial energy transfer. Handover does not guarantee that the field
will persist: subsequent passive self-excitation depends on speed and capacitance.
All support power, losses and battery depletion enter the existing balances.

Selecting **Residual magnetism** supplies a 0.005 Wb illustrative initial seed
when the configured seed is zero. A positive user-configured seed is retained;
**Zero flux** explicitly starts without a seed. The magnetic-field inset uses
logarithmic brightness to reveal small residual fields, with true measured Wb
and percentage printed alongside it. It does not change the simulated flux.

Click the **CHARGER** card to enable or disable the DC-link-to-24-V charger.
The setting takes effect in the physical power path immediately, without
resetting time or energy states. OFF means zero charger input, output and heat;
it does not disconnect the separate battery-to-boost path. ON permits charging
subject to the existing DC voltage, battery current and SOC limits.
