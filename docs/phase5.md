# Phase 5: averaged rectifier, DC bus and equivalent brake resistance

**Question:** How does a passive rectifier and DC resistive load affect
excitation, DC voltage, generator braking, lowering speed and energy dissipation?

The default UI now enables this path. It replaces the Phase 4 balanced AC test
resistor, rather than adding a second load. Turn off **Rectifier + DC brake**
in Explore to restore that earlier load; this changes topology and resets the run.
The **DC brake** slider changes equivalent resistance live, retaining flux,
voltage, motion, history and cumulative energy. Lower resistance draws more
current at a given voltage; the resulting voltage/excitation may also change,
so it does not guarantee greater steady braking.

## Model and estimates

For an averaged three-phase diode bridge, use
`E = (3 sqrt(2) / pi) V_LL,RMS`, approximately `1.35 V_LL,RMS`.
This is an average-value approximation, not capacitor-input peak charging or
six-pulse ripple. See [MathWorks' averaged rectifier analysis](https://www.mathworks.com/help/sps/ug/harmonic-analysis-of-a-three-phase-rectifier.html)
and [average-value rectifier model](https://www.mathworks.com/help/sps/ref/averagevaluerectifierthreephase.html).

The additional equations are:

```
I_bridge = max((E - V_DC) / R_source, 0)
C_DC dV_DC/dt = I_bridge - V_DC/R_brake
P_AC = E I_bridge
P_DC_in = V_DC I_bridge
P_bridge/source_loss = R_source I_bridge²
P_brake = V_DC² / R_brake
E_DC = 0.5 C_DC V_DC²
```

The bridge cannot return DC energy to AC. AC current is represented by an
in-phase fundamental vector chosen so `1.5 Re(v conj(i_bridge)) = P_AC`.
Its current is included in the AC capacitor differential equation and inverter
current balance. Thus DC loading affects excitation and torque through the
machine circuit; it is not an independent cosmetic power calculation.

Estimated defaults, all in `Parameters`:

| Parameter | Default | Meaning |
| --- | --- | --- |
| DC capacitance | 470 µF | DC-link storage, separate from AC excitation capacitors |
| Initial DC voltage | 0 V | Included in initial stored energy if changed |
| Effective bridge/source resistance | 10 ohm | Finite charging-current impedance and explicitly counted loss |
| Equivalent brake resistance | 390 ohm | Continuously connected resistor, adjustable live |
| Motor rated line voltage | 400 V RMS | Display reference independent of the exciter frequency command |

At 400 V AC, the model's steady values are approximately 526.7 V DC,
711 W brake heat and 18.2 W effective bridge/source loss. These are illustrative
operating values, not component ratings. The 10-ohm effective resistance is an
assumed lumped source impedance, not a measured diode resistance.

With the 300 kg example starting at 1530 RPM, after 1 simulated second with the
exciter ON: approximately 16.27 m/min, 400 V AC and 526.7 V DC. After another
0.5 simulated second with the exciter OFF: approximately 17.98 m/min, 407 V AC
and 535.7 V DC. This illustrates that electrical generation does not necessarily
mean the speed is already steady. It is not a speed controller.

## Visuals and accounting

The overview adds diode passing/blocked feedback, a one-way DC power path,
DC voltage and stored joules, and instantaneous resistor heat in watts.
The cumulative energy inventory adds DC storage, DC brake heat and
bridge/source heat. Internal rectifier transfer is not counted as another sink.
The balance includes initial DC energy and the ideal exciter's signed external
energy. Details includes DC telemetry and four additional history plots.

The main AC voltage bar is now linear: 200 V on a 400 V motor means 50%,
regardless of capacitance or the exciter frequency setting. AC capacitor storage
is displayed separately in joules. Percentages may exceed 100%; the visual fill
is capped, but there is no simulated voltage clamp or rating protection.

## Validation and review boundary

Tests check one-way conduction, instantaneous bridge power balance, analytical
DC capacitor discharge into a resistor, steady DC voltage, time-step convergence,
coupled cumulative energy accounting, live resistance changes and voltage-bar
scaling. The small-hoist handover was also checked with a five-times tighter
electrical rate bound; DC voltage agreed to less than 0.001 V.

This averaged passive model requires nonzero connected AC capacitance when
the exciter is OFF. Removing all AC storage requires a different commutation /
open-circuit treatment; the UI rejects that combination rather than introducing
spurious numerical energy. With the exciter ON, the no-AC-capacitor case remains
supported. Phase 4 AC test-load comparisons remain available.

There is no chopper switching, duty-cycle controller, resistor thermal model,
power rating limit, diode harmonics, commutation inductance or DC-dependent
exciter yet. In particular, the ideal exciter is still an external unlimited
source/sink; it is **not powered from this DC link**. Phase 6 will add the brake
chopper's control dynamics after review of this phase.
