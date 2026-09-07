# Instantaneous and accumulated conservation

Reviewed against HEAD `3b290f5ef650abb53bc0a31faca7201975731b84`.
The running topology is `ExternalLoweringModel` (the historical class name is
retained for compatibility). Its only energy inputs are initial stored energy
and decreasing load height. `external_supply_voltage` is a legacy parameter
and cannot supply this model.

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
| Rectifier / source impedance | P_ac | V_dc I_rect | P_ac - V_dc I_rect | 0 |
| DC link | V_dc I_rect | P_chopper + P_charger | 0 | C_dc V_dc dV_dc/dt |
| Ideal averaged chopper | duty V_dc²/R_brake | same | 0 | 0 |
| Brake resistor | duty V_dc²/R_brake | 0 | same | 0 |
| Exciter | P_boost,out | Re(S_exciter) | 3/2 R_out abs(i_exciter)² + idle + max(0,-P_exciter) | 0 |
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
E_dc = 1/2 C_dc V_dc²
```

The magnetic derivative is evaluated from the winding state derivatives, not
created by subtracting displayed power readings. Tests also check it against a
finite difference of the energy function. Capacitor Q describes exchange with
the field and never enters a real-power or accumulated-energy residual.

## Exciter-only constraint and voltage capability

There is no AC capacitor state in exciter mode. A flux-magnitude controller
commands a Thevenin voltage behind the configured output resistance, with
winding-current feedforward. The command uses the actual flux direction so
current limiting can change field phase without destabilizing the controller.

Every integration stage solves the two real equations
`i_exciter = i_stator + v/R_core + i_rectifier` for terminal voltage.
The current evaluator applies RMS current, AC active power, reverse absorption,
boost input/output power, and modulation capability limits *inside* that solve.
Terminal voltage is not integrated from an unlimited requested derivative.
If a feasible conducting converter point cannot be found, the exciter blocks
and the passive core/bridge network determines voltage and absorbs the winding
energy. The KCL residual remains visible in diagnostics.

The balanced inverter's linear modulation ceiling is
`abs(v + R_out i_exciter) <= V_boost / sqrt(3)`. The normal example now uses a
600 V auxiliary boost output; 520 V did not provide linear modulation headroom
for the normal field plus winding/output voltage drops. This auxiliary output
is separate from the approximately 524 V brake DC link. Its current ceiling is
`P_boost,out / V_boost <= boost_output_current_limit`.

The charger enables at 480 V in the normal example. The old 50 V setting could
load startup with a 150 W constant-power charger before useful generation.
Both voltage settings remain configurable. Battery limitations can still
prevent startup; the controller does not manufacture missing real power.

## Battery, boost and charger

The battery is a finite, constant-open-circuit-voltage energy store with series
resistance: `V_t = V_oc - R I`, `P_terminal = V_t I`.
The low-current root of this equation determines signed current, including
simultaneous boost demand and charger output. Thus terminal voltage rises on
charge and falls on discharge; internal heat is always nonnegative.

Boost input is bounded by discharge current, the battery's maximum-power point,
remaining chemical energy over the integration step, converter input power,
efficiency, and high-voltage output current. Limiting occurs before electrical
integration. The charger limits *net battery charge current* and chemical
headroom, while allowing simultaneous boost use. SOC is not clipped after
integration to hide missing energy.

## Reset, integration and limitations

Precharge is an explicit initialization transfer, not a time-resolved switching
sequence. AC energy is `1/2 C_ac V_LL²`, bounded by finite battery energy and the
boost voltage capability. Battery removal is `E_ac / precharge_efficiency`;
the difference is accumulated precharge heat. The initial-energy reference is
the post-transfer inventory **plus that heat**, giving zero reset residual.
The configured precharge efficiency represents the complete initialization
transfer; no instantaneous precharge current is claimed at t=0.

The accumulated residual is current height + kinetic + magnetic + AC capacitor
+ DC capacitor + battery energy, minus initial inventory, plus every accumulated
heat term (including battery I²R, precharge and impact). No Q appears in it.
RK steps reject/subdivide when their AC/magnetic energy change disagrees with
integrated physical work. This resolves stiff winding decay after converter
blocking; it does not correct the state energy cosmetically.

This remains a balanced, averaged fundamental model. It does not resolve diode
harmonics, switching ripple, battery electrochemistry, or individual cell
voltages. `Pac - Pdc` is **rectifier/source loss**, because the configured
resistance includes source impedance as well as the bridge.

Run `python -m simulation.power_review` for component tables at reset, startup,
acceleration and steady lowering, plus capacitor-only snapshots. Run
`python -m simulation.preview_energy` for previews rendered from the actual Tk
canvas geometry at the normal application size with its sidebar present.
