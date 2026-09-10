# Architecture-valid averaged topology

The primary `ExternalLoweringModel` explicitly represents the components and
stored energies that materially affect startup, excitation, energy transfer,
protection sequencing and first-pass hardware sizing. It remains a balanced,
fundamental-frequency, averaged model: it does not simulate PWM, diode switching
waveforms, EMC, detailed battery chemistry or flexible mechanics.

```text
                         DELTA CAPACITOR BANK
                                  |
                                K_CAP
                                  |
LOAD -> GEAR -> INDUCTION MACHINE -> AC BUS -> DIODE BRIDGE
                                  |                    |
                                K_EXC           K_PRECHARGE--R_PRECHARGE
                                  |                    |       || K_MAIN
                           EXCITER INVERTER             +-------+
                                  |                    |
                                C_AUX                 C_DC
                                  |                    |
                                BOOST       CHOPPER -> RESISTOR
                                  |                    |
                             24 V BATTERY <- CHARGER <-+
```

## Exciter and auxiliary supply

Real power is one-way: `battery -> boost -> C_aux -> inverter -> AC bus`.
The inverter AC active-current component is constrained to be nonnegative in
the network equations, so generated real power cannot enter the inverter or
auxiliary link. Reactive current is bidirectional and has its own component
limit in addition to the total RMS-current limit.

During field building the configured `exciter_active_limit` permits magnetic
energy buildup and electrical losses. After the brake-release command, the
lower `exciter_run_active_limit` participates in the same AC solve and prevents
intentional material motoring. It is not a display clamp. Modulation capability
uses the instantaneous dynamic `V_aux`, not the boost target.

`inverter_output_resistance` is controller/virtual impedance. Its voltage drop
shapes the feasible current command but does not become heat. Physical converter
heat is `1.5 R_conduction |i|^2 + P_idle`, using
`inverter_conduction_resistance`.

The boost has finite input power, battery current, high-side current, efficiency
and current-command response. `C_aux` stores `0.5 C_aux V_aux^2`; boost output
charges it and inverter DC input discharges it. Starting from zero volts uses a
bounded discrete energy solve, so there is no hidden infinite HV source.

## Main DC-link connection

With the main DC path enabled, `K_PRECHARGE` is closed from reset and the bridge
sees `C_dc` through the real `R_precharge`. There is no AC-voltage, exported-power,
motor-rating or startup-readiness permission in the passive conduction path.
The bridge conducts whenever the rectified instantaneous source exceeds `V_dc`;
otherwise its diodes block. When `V_dc` reaches the configured fraction of the
present rectified crest, the controller commands the physical `K_MAIN` bypass
contactor. A timeout latches an explicit protection fault and commands brake
application. `ControlInputs.main_dc_enable` commands isolation through these
contactors, and `main_bypass_command` can explicitly hold the resistor path or
command the bypass for commissioning/tests.

The averaged precharge-resistor loss is separated from bridge/source loss and
accumulated in `dc_precharge_loss_energy`. The chopper remains physically across
`C_dc` in every contactor state and responds to actual link voltage. No contact
bounce or diode/PWM ripple is represented.

## Startup modes

Exciter startup proceeds through auxiliary-link charging, low-frequency flux
building with the brake held, brake-release command, frequency ramp and natural
transition through synchronous speed into generation. Rotor speed and slip are
never forced. `ControlInputs.speed_request_hz` is the future potentiometer/
operator frequency request; it defaults to the parameter value.

The optional canonical profile continues through `LOWERING` (20 Hz),
`SLOWDOWN_1` (15 Hz), `SLOWDOWN_2` (10 Hz), `SLOWDOWN_3` (7.5 Hz),
`SLOWDOWN_4` (5 Hz), and `BRAKE_APPLY`. Frequency changes
use configured ramps. Excitation remains connected until physical brake feedback
and low speed qualify `STOPPED`. Capacitor-only mode shares these brake/fault
states but receives no frequency or voltage command. Its common chopper target
uses estimated actual electrical frequency instead.

In capacitor-only residual startup, `K_CAP` is closed, `K_EXC` is open and the
brake is commanded to release immediately. Rotation is therefore available to
turn residual flux into terminal voltage; field qualification is not awaited at
standstill. Zero residual flux remains zero in this deterministic model.

For the precharged-bank case, the capacitor bank is defined as connected to the
machine during the finite, lossy initialization transfer from the 24 V battery.
The main DC link is still connected through `K_PRECHARGE` and `R_precharge`; diode
polarity alone decides whether the charged AC bank transfers energy into it. The
initial energy inventory includes capacitor energy, battery depletion and
precharge heat, so reset does not create energy.

## Brake and controller interface

`brake_released` is a command, while `State.brake_fraction`,
`brake_physical_state` and `brake_physically_released` describe the actuator.
Release delay, application delay and torque response are independent parameters.
The automatic sequence writes the command; the brake remains a distinct physical
component.

`ControlInputs` exposes master on/off, start/lower, stop, emergency stop,
frequency request and optional brake override. Physics telemetry exposes switch
states and lamp-ready signals for control power, battery, auxiliary HV, field,
AC bus, main DC link, brake, lowering, fault and chopper activity. A future panel
can bind to these signals without placing fake control behavior in the UI.

## Solver status

The clipped two-axis AC KCL uses continuation from the previous terminal voltage,
bounded Newton steps, multiple physical seeds and a derivative-free bounded
fallback. Telemetry distinguishes `SOLVED`, `LIMIT_REACHED`,
`CONVERTER_BLOCKED`, `PHYSICALLY_INFEASIBLE_BLOCKED`, `PASSIVE` and `DYNAMIC`.
A failure outside the explicitly recognized limit-block condition raises
`ExciterSolverError`; numerical nonconvergence is not silently treated as a
physical switch-off.

## Sizing telemetry

`readings()` and `power_diagnostics` provide the physics-derived instantaneous
quantities for battery, boost, auxiliary link, exciter P/Q/current components,
capacitor bank, rectifier, main DC capacitor, chopper/resistor and charger.
Use `python -m simulation.architecture_demo` to produce the sampled time history,
peak table and plot in [architecture-demo.md](architecture-demo.md).
