# Canonical capacitor lowering review


Capacitor-only frequency is emergent; no 20/10/5 Hz commands are applied.

- Natural trajectory status: unstable/runaway
- Speed: 59.625 m/min; rotor: 5693.72 rpm; electrical frequency: 152.65 Hz; slip: -0.2433
- Voltage/current/flux: 273.64 V LL / 2.938 A / 0.164 Wb
- Motor active/reactive current: -1.093 / 2.728 A
- Capacitor current/Q: 2.728 A / 1292.74 var
- Generating torque/mechanical input: 1.522 N m / 907.69 W
- Copper/core/magnetic-storage power: 360.53 / 18.72 / 10.35 W
- Export/rectifier/DC/resistor: 518.10 / 507.53 / 478.20 / 0.00 W
- Chopper duty: 0.00%
- DC link/capacitor power: 359.41 V / 478.20 W

Conclusion: this passive capacitance does not reach a safe stable lowering equilibrium before protection acts.

- Final state: `FAULT`; fault: `RUNAWAY DIAGNOSTIC`
- Final energy residual: +0.00015673 J
