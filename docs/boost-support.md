# 24 V startup and backup support

The boost is now an auxiliary source on the shared main DC bus. It remains
available during lowering and supplies current again when voltage falls below
its target. It cannot accept reverse power from the main bus.

The default UI uses **24 V startup**: zero DC precharge, zero residual-flux
seed, stationary load, mechanical brake held and exciter OFF. Start the example,
let the boost charge the bus, then enable excitation and release the brake
manually to explore lowering. This is not yet an automatic startup sequencer.
Other seed demos disable boost so they remain meaningful capacitor-only tests.
The handover example retains its stated 600 V precharge and enables backup.

## Estimated parameters

| Input | Default |
| --- | --- |
| Battery voltage | 24 V |
| Maximum battery input power | 200 W (8.33 A at 24 V) |
| Boost efficiency | 90% |
| High-voltage output current limit | 1 A |
| DC support target | 520 V |
| Current-command response | 50 ms |
| Voltage-loop gain | 0.02 A/V |
| Chopper starting threshold | 560 V |

The voltage target and battery-power limit have live Explore sliders. The boost
enable checkbox acts live and retains stored energy/history. The UI requires
at least 20 V between boost target and chopper starting threshold, rejecting
changes that overlap those settings. The 20 V margin is an illustrative control
constraint, not a calculated equipment-design margin.

## Averaged equations

```
I_available = min(I_output_max, efficiency P_battery_max / max(V_DC, V_battery))
I_command = min(I_available, max(0, gain (V_target - V_DC)))
dx/dt = (I_command - x) / response_time
I_output = min(max(x, 0), I_available)
P_output = V_DC I_output
P_battery = P_output / efficiency
P_loss = P_battery - P_output
I_battery = P_battery / V_battery
```

When disabled, the current command and actual output are zero. At or above
the target, output isolation blocks injection even while the internal command
state decays. That state is a controller state, not stored inductor energy.
The current limit makes charging from zero volts finite; the power limit is
enforced on actual output, including during transients. No switching converter,
battery voltage sag, finite battery capacity, or cell chemistry is modeled.
Battery consumption is accumulated in joules and displayed in Wh.

Battery energy is added to the cumulative energy budget separately from the
earlier ideal-exciter external-energy counter. Boost losses are a separate heat
destination. The DC balance receives actual boost output current. No battery
energy or losses are attributed to the descending load, and disabling the boost
does not erase prior usage/losses.

## Avoiding continuous battery-to-resistor heating

The boost regulates below the chopper threshold. It goes to standby when
generated voltage is high enough, while the chopper remains independently able
to dissipate high-bus-voltage energy. There is no rule that disables braking
merely because battery support is requested. On a shared bus, energy mixes;
this coordination avoids deliberate steady opposing regulation, but does not
promise zero battery-origin energy in the resistor during every transient.

## Checks and limits

In a no-excitation charging check, after 3 simulated seconds the default bus
reached approximately 520.01 V. Battery input was 70.61 J, boost was in standby,
and brake-resistor energy was exactly zero. The small voltage excess is numerical
crossing of the output cutoff, not another regulation target.

A manual startup check enabled the exciter at 3 s and released the brake at
3.5 s. By 6 s, the model reached approximately 16.27 m/min, 400 V AC and
589.37 V DC, with the boost in standby and resistor heating around 654 W.
The DC voltage dipped strongly while energizing the stationary machine: this
limited auxiliary source cannot maintain rated voltage at locked rotor. Do not
interpret it as a full-power motor supply or expect 400 V AC while holding the
motor stationary. The startup check is an illustrative trajectory, not a
validated equipment sequence.

Automated checks cover limits, efficiency accounting, reverse blocking, standby
and renewed demand after a voltage drop, empty-bus charging without resistor
heat, reset, retained energy after disable, and timestep convergence. The startup
sequence and battery-sizing/thermal/fault models remain separate future work.
