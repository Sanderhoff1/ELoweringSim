# Estimated 0.9 kW geared hoist

The UI now starts with a 300 kg load at 200 m, using a four-pole, 400 V,
50 Hz motor estimate. Library defaults are retained for earlier model tests.
All guided examples use this same hoist. The normal startup is stationary;
the guided excitation examples start at 1530 RPM (16.0 m/min) and explicitly
include that initial kinetic energy in the budget.

These are estimates, not a particular manufacturer's motor specification.
Four poles at 50 Hz gives 1500 RPM synchronous speed; 1420 RPM is the assumed
rated motoring speed. See the [WEG motor-data explanation of synchronous
speed and slip](https://static.weg.net/medias/downloadcenter/h99/h2d/WEG-WAE-IT-1S95SWEN-en.pdf).

| Assumption | Value / rationale |
| --- | --- |
| Rated shaft output | 900 W; approximately 6.05 Nm at 1420 RPM |
| Drum and gearing | 0.10 m radius, ideal 60:1 ratio; effective radius 0.001667 m/rad |
| Load speed at 1420 RPM | 14.87 m/min |
| Gravity torque referred to motor | 4.905 Nm |
| Initial height energy | 588.6 kJ (0.1635 kWh) |
| Shaft inertia excluding suspended mass | 0.008 kg m², including estimated reflected drivetrain inertia |
| Mechanical brake | 10 Nm, 0.2 s actuator response |
| Viscous damping | 0.001 Nm s/rad; no separately modeled gear efficiency |
| Star-equivalent winding resistance | Rs = 7 ohm, referred Rr = 7.35 ohm |
| Leakage inductances | 0.025 H each |
| Magnetizing inductance | 0.65 H with saturation-flux scale 1.8 Wb turn |
| Delta capacitors | 6 µF per branch; estimate, not guaranteed self-excitation |
| AC test load | 220 ohm per star phase; about 727 W at 400 V line-line |
| Precharge example | 200 V equivalent line RMS |

The dynamic circuit gives approximately 901 W shaft output in a fixed-speed
1420 RPM, 400 V test after one second. This anchors one operating point only;
it does not identify a motor's complete equivalent circuit or enforce a 900 W
power limit. The steady-mode fallback uses an estimated 15 Nm peak torque.
The ideal exciter can source and absorb real power without a rating limit.

## Energy inventory

The stacked bar and destination tracks share one absolute energy scale:

`initial height + initial kinetic/magnetic/capacitor energy + net exciter input`

equals

`remaining height + kinetic + magnetic/capacitor energy + AC load heat
 + copper heat + brake/friction/impact + net energy returned to exciter`.

Net exciter input and net returned energy are mutually exclusive signed totals,
not gross import/export counters. The displayed balance error is the numerical
residual, not a loss category. Tiny destinations retain numeric kJ labels instead
of being enlarged misleadingly. Since energy sources mix, the display does not
claim all heat came from the load. Reactive paths indicate exchange and are not
added as consumed energy. This cumulative inventory is available in dynamic mode.

The diagram stretches to the available width and height. Text has a 15 px minimum;
smaller windows scroll instead of shrinking the text. Excitation is routed above
the machine-to-bus connection. Speed is signed m/min, positive for lowering.
