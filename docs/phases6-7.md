# Phases 6 and 7: chopper control and DC-fed excitation

The Explore mode selector retains three comparisons:

- **5 · Direct resistance:** previous averaged rectifier and equivalent DC resistor.
- **6 · Chopper + ideal exciter:** controlled resistor duty; ideal external excitation.
- **7 · DC-fed exciter:** controlled duty plus a bounded, lossy exciter drawing
  from the same DC capacitor. This is the new UI default.

Mode/topology changes reset the run. Resistor resistance, chopper threshold,
exciter current limit, chopper enable and exciter enable act live. The UI rejects
removing the DC link or AC capacitor bank in Phase 7; select an earlier mode for
those comparisons. Library model defaults remain in the earlier modes for compatibility.

## Phase 6 question and equations

**Question:** How do chopper threshold, finite response and maximum duty affect
DC voltage and the heat absorbed by the brake resistor?

This is a proportional voltage-band controller with a first-order duty response,
not a PI controller and not switching-level PWM:

```
d_command = clamp((V_DC - V_start) / voltage_band, 0, d_max)
dd/dt = (d_command - d) / response_time
I_brake,average = d V_DC / R_brake
P_brake,average = d V_DC² / R_brake
```

Disabling the chopper sets its duty request to zero; actual duty decays with the
same response time. It therefore does not instantaneously remove resistor power.
The power uses duty times voltage squared, not squared average voltage.
This follows an [average-value chopper representation](https://www.mathworks.com/help/sps/ref/averagevaluechopper.html).
The voltage-band approach is also described in [JCS chopper controller documentation](https://jcsdoc.arbite.io/latest/devices/JCS0005_dev_braking_chopper/JCS00050002010000/sw_reference/braking_chopper_ext_controller/).

Estimated defaults are 560 V start, 40 V band, 20 ms response and 100% maximum
duty. There is expected steady voltage rise above the starting threshold under
load. Duty saturation is reported, not prevented by an artificial voltage clamp.
Chopper semiconductor loss and resistor temperature are not modeled.

The Phase 6 guided examples use a 500 V starting threshold so the chopper can
operate below the approximately 540 V rectifier output from the ideal 400 V AC
source. That source can still supply or absorb power externally in Phase 6.

## Phase 7 question and equations

**Question:** Can excitation be maintained with the available DC voltage and a
finite converter current rating, and how much energy does the converter use?

The previous V/f bus-voltage controller computes a requested AC current. The
converter is modeled as an averaged controllable voltage `u` behind an effective
output resistance `R_out`:

```
u_requested = v_AC + R_out i_requested
|u| <= V_DC / sqrt(3)
|i| <= sqrt(2) I_limit,RMS
i = (u - v_AC) / R_out
P_AC = 1.5 Re(v_AC conj(i))
P_loss = 1.5 R_out |i|² + P_idle
P_DC = P_AC + P_loss
C_DC dV_DC/dt = I_rectifier - d V_DC/R_brake - P_DC/V_DC
```

The phase-peak voltage ceiling is the linear space-vector-modulation limit;
equivalent line RMS is `V_DC/sqrt(2)`. See [MathWorks' two-level PWM documentation](https://www.mathworks.com/help/sps/ref/pwmgeneratorthreephasetwolevel.html).
Current and voltage commands are projected into the intersection of their two
feasible disks. Both limits are respected simultaneously, rather than clipping
current in a way that silently demands an impossible converter voltage.

If AC bus voltage is too high for any feasible bounded-current command, the
model uses an **ideal isolation block**. It does not model uncontrolled
antiparallel-diode conduction. The diagram reports `AC too high: blocked`.
This explicit approximation is part of the converter model, not a prediction
of a real drive's overvoltage protection behavior.

Below the minimum DC voltage or when switched OFF, converter current and loss
are zero. The converter can return AC energy to DC; its losses reduce that return.
All terminal current limits refer to the balanced phase RMS fundamental.

Estimated defaults: 3 A RMS limit, 5 ohm effective output/conduction resistance,
3 W overhead, and a 50 V minimum DC operating voltage. The resistance is a
lumped estimate, not a measured semiconductor parameter. There are no switching
harmonics, filter inductance, thermal states, gate delays, or manufacturer-fitted
loss maps.

## Initial energy and guided experiment

The normal UI and Phase 7 **Exciter handover** use a 600 V initial DC precharge.
At 470 µF this is **84.6 J**, counted in initial stored energy. Other seed demos
start with zero DC voltage and the exciter OFF; their residual AC flux or AC
capacitor precharge is retained as previously defined.

No bootstrap converter or startup sequencer has been added. The initial charge
is a stated initial condition, not an unlimited supply. In Phase 7, the external
source-energy counter stays zero even while AC power flows through the exciter:
that is internal energy exchange with DC storage.

For a baseline, keep the exciter ON in the handover example. Switching it OFF
is a separate capacitor-only experiment. `DC TOO LOW` means commanded ON does
not imply current is available; raising the current limit cannot create a DC
supply. Feedback distinguishes an empty starting condition from field collapse
using the retained flux history. The residual-flux parameter is only an initial
condition, not persistent magnetic remanence/hysteresis: a decayed seed is not
re-created automatically at a higher speed. These startup results therefore
cannot establish whether a particular real motor will self-excite reliably.

Select **7 · DC-fed exciter**, start **Exciter handover**, and watch the outer
DC-to-exciter path, duty bar and current-limit indicator. After 0.5 simulated
seconds with the default moving load, one check gave approximately 589.37 V DC,
399.98 V AC, 73.41% duty and 653.85 W resistor heat. These are model examples,
not guarantees of a steady state. Lower the current limit to see the field/
voltage response, or change the chopper threshold while watching DC energy.

The overview separates duty request saturation from actual duty reaching its
limit. Details includes duty, converter DC power and converter-loss histories.
The cumulative energy budget adds exciter heat and counts DC-to-AC exchange
only internally, so it cannot double-count that power as external input.

## Validation and review boundary

Tests cover threshold and saturation behavior, exact disabled-duty decay,
simultaneous current/voltage bounds over varied complex-vector conditions,
regeneration accounting, zero-charge/no-hidden-source startup, Phase 6 operation,
Phase 7 energy balance, live control changes, reset and timestep convergence.

The next planned phase is **8: startup sequence**. Phase 9 adds 24 V bootstrap;
Phase 10 adds fault/limit cases. Those phases remain unimplemented for review.
