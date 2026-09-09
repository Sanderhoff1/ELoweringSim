# Hidden-switch audit

Audit scope: all Python model, controller, UI and diagnostic paths in the
repository. A zero caused only by arithmetic at zero voltage/current is not a
topology decision and is grouped with its governing physical equation.

| Case | Class | Result |
|---|---|---|
| Diode bridge forward/reverse decision in `capacitor_rectifier.transfer` and `rectifier.bridge` | A — passive physics | Kept. Conduction is based only on rectified AC crest, DC voltage and physical series resistance; there is no minimum AC voltage. |
| Main-link `R_precharge` | A — passive physics | Kept. It is present whenever `K_PRECHARGE` is closed and its heat is accumulated separately. |
| `K_PRECHARGE` / `K_MAIN` | B — real hardware switch | Kept and made explicit. DC-path enable commands `K_PRECHARGE` immediately; `K_MAIN` is the physical resistor bypass. Both states are telemetry and schematic labels. |
| Export-power, 50 V AC and `electrically_ready` permissions for `K_PRECHARGE` | D — artificial simulation heuristic | Removed. They can no longer isolate the passive bridge. |
| `K_MAIN` permission in the chopper-duty command | D — artificial simulation heuristic | Removed. Chopper control uses actual `V_dc` and its own explicit enable only. |
| Chopper voltage band, response, maximum duty and enable | C — real controller/protection interlock | Kept. It commands a physical semiconductor switch across `C_dc`; resistor power is `duty V_dc^2/R`. |
| `K_CAP` and `K_EXC` excitation selection | B — real hardware switch | Kept as explicit switchgear state. Their states control the corresponding capacitor/inverter branches and appear in telemetry/schematic. |
| Exciter `V_aux` readiness requirement and modulation/current/power limits | C — real controller/protection interlock | Kept. The inverter cannot switch below its auxiliary-link operating voltage or outside its physical limits. |
| Exciter nonnegative active-current constraint | C — real converter topology/control | Kept. AC-to-exciter real-power regeneration is blocked, while signed reactive current remains possible and DC input equals AC output plus loss. |
| Boost target/limits, battery depletion and converter enable | C — real controller/protection interlock | Kept. `C_aux` charging follows its energy equation; no hidden HV source exists. |
| Battery charger minimum `V_dc`, SOC, charge-current, power and efficiency limits | C — real converter operating range | Kept. Below minimum input voltage the DC/DC converter cannot operate. |
| Brake release/application command, delays and actuator fraction | B/C — physical brake plus real controller | Kept. Software issues commands; delayed physical state and torque remain independent. |
| Startup flux qualification and support handover | C — real controller interlock | Kept. It may command the brake and `K_EXC`, but does not gate bridge conduction or erase passive state. |
| Master/stop/emergency controls | B/C — commanded physical switch/protection | Kept. Emergency/master-off commands the modeled contactors and exciter switch; stop commands the physical brake. |
| Legacy `motor_connected`, `rectifier`, capacitor and converter UI toggles | B/C — explicit comparison-mode hardware/control | Kept. They are user-visible component connection/controller selections, not inferred startup readiness. |
| Open-stator and grounded-load zero derivatives | A/B — physical boundary/topology | Kept. Open winding current and ground-contact motion are explicit physical boundary conditions. |
| Numerical step rejection/subdivision and solver errors | Numerical only | Kept. They refine or reject an invalid integration step and never silently open a physical branch. |

After the two category-D cases above were removed, no startup/readiness heuristic
in the primary model suppresses physically possible passive rectifier or chopper
power flow.
