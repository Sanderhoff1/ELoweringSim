# Final reviewed topology

The reviewed model has two exclusive modes.

```text
LOAD -> GEAR / BEARINGS -> INDUCTION MACHINE -> AC BUS -> DIODE RECTIFIER
     -> DC LINK -> CHOPPER -> BRAKE RESISTOR
```

In **Exciter only**, AC capacitors are absent (`C = 0`) and a controlled
exciter supplies the AC bus. Its only energy source is the finite 24 V battery
through an averaged boost converter. In **Capacitor only**, the exciter is
open-circuit and the induction machine/capacitor dynamic states determine bus
voltage and frequency. The permitted starts are residual magnetic flux and,
for capacitor-only, a lossy 24 V precharge transfer.

The diode bridge, DC link, chopper, and brake resistor are always connected.
An averaged, loss-bearing DC/DC charger transfers available DC-link energy to
the finite 24 V store without reverse flow or overcharge. All energy sources,
stores, transfers and heat losses are reported in the model telemetry.
