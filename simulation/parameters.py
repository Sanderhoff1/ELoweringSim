"""All physical inputs; defaults are illustrative, not crane specifications."""
from dataclasses import dataclass, field, fields
import math


def parameter(default, unit, meaning, status="placeholder", minimum=0.0, maximum=1e6):
    return field(default=default, metadata=dict(unit=unit, meaning=meaning,
                 status=status, minimum=minimum, maximum=maximum))


@dataclass(frozen=True)
class Parameters:
    mass: float = parameter(100.0, "kg", "Suspended load mass", minimum=0.001)
    radius: float = parameter(0.1, "m/rad", "Load travel per motor-shaft radian; drum radius / gear ratio", minimum=0.0001, maximum=100)
    inertia: float = parameter(1.0, "kg m²", "Rotational inertia at shaft, excluding suspended mass")
    damping: float = parameter(0.2, "N m s/rad", "Viscous shaft friction coefficient")
    brake_torque: float = parameter(150.0, "N m", "Static and sliding brake torque capacity at shaft")
    brake_response: float = parameter(0.3, "s", "Brake application/release time constant (0 = instantaneous)", maximum=60)
    crane_height: float = parameter(10.0, "m", "Initial clearance below load; maximum downward travel", minimum=0.01, maximum=10000)
    gravity: float = parameter(9.81, "m/s²", "Constant gravitational acceleration", "estimated", maximum=100)
    supply_frequency: float = parameter(5.0, "Hz", "Ideal rotating-field frequency, lowering direction", minimum=0.1, maximum=100)
    pole_pairs: float = parameter(2, "pairs", "Motor pole pairs (integer; 2 pairs = 4 poles)", minimum=1, maximum=20)
    peak_motor_torque: float = parameter(120.0, "N m", "Peak magnitude of the assumed torque-slip curve", maximum=10000)
    peak_slip: float = parameter(0.2, "1", "Slip magnitude at peak motor/generator torque", minimum=0.01, maximum=1)
    volts_per_hz: float = parameter(8.0, "V/Hz", "Commanded line-line RMS voltage / frequency", maximum=100)
    reference_volts_per_hz: float = parameter(8.0, "V/Hz", "V/f at which the peak torque parameter is defined", minimum=0.1, maximum=100)
    magnetizing_inductance: float = parameter(0.2, "H/phase", "Linear star-equivalent magnetizing inductance", minimum=0.001, maximum=100)
    capacitor_capacitance: float = parameter(1000.0, "µF/branch", "Each of three delta-connected AC capacitors", maximum=100000)
    stator_resistance: float = parameter(0.5, "ohm/phase", "Dynamic model: stator winding resistance", minimum=0.01, maximum=100)
    rotor_resistance: float = parameter(0.4, "ohm/phase", "Dynamic model: rotor resistance referred to stator", minimum=0.01, maximum=100)
    stator_leakage: float = parameter(0.01, "H/phase", "Dynamic model: stator leakage inductance", minimum=0.001, maximum=1)
    rotor_leakage: float = parameter(0.01, "H/phase", "Dynamic model: referred rotor leakage inductance", minimum=0.001, maximum=1)
    saturation_flux: float = parameter(1.0, "Wb turn", "Flux where nonlinear magnetizing current is twice its linear value", minimum=0.01, maximum=10)
    initial_flux: float = parameter(0.005, "Wb turn", "Initial residual-flux seed; initial condition, not a hysteresis model", maximum=1)
    precharge_voltage: float = parameter(0.0, "V LL equiv.", "Initial capacitor-voltage vector as equivalent line RMS", maximum=1000)
    initial_shaft_rpm: float = parameter(0.0, "RPM", "Dynamic model: shaft speed at Reset", maximum=3000)
    ac_load_resistance: float = parameter(100.0, "ohm/phase", "Balanced star AC test load; larger values mean lighter load", minimum=1, maximum=100000)
    excitation_response: float = parameter(0.05, "s", "Ideal inverter voltage-establishment time constant", minimum=0.001, maximum=1)
    motor_rated_voltage: float = parameter(400.0, "V LL RMS", "Nameplate voltage; reference for the overview voltage bar", "estimated", minimum=1, maximum=1000)
    dc_capacitance: float = parameter(470.0, "µF", "DC-link smoothing capacitor", "estimated", minimum=10, maximum=100000)
    dc_initial_voltage: float = parameter(0.0, "V", "Initial DC-link voltage at reset", "estimated", maximum=1500)
    rectifier_resistance: float = parameter(10.0, "ohm", "Effective averaged bridge/source resistance; limits charging current", "estimated", minimum=1, maximum=1000)
    dc_brake_resistance: float = parameter(390.0, "ohm", "DC equivalent brake resistance; smaller draws more current at a given voltage", "estimated", minimum=10, maximum=100000)
    chopper_threshold: float = parameter(560.0, "V DC", "Chopper starts requesting duty above this DC voltage", "estimated", minimum=10, maximum=1500)
    chopper_band: float = parameter(40.0, "V", "Voltage rise above threshold for a full-duty request", "estimated", minimum=1, maximum=500)
    chopper_response: float = parameter(0.02, "s", "Averaged chopper duty response time constant", "estimated", minimum=0.001, maximum=1)
    chopper_max_duty: float = parameter(1.0, "fraction", "Maximum allowed resistor duty", "estimated", maximum=1)
    inverter_current_limit: float = parameter(3.0, "A RMS", "Phase current limit of DC-fed exciter", "estimated", minimum=0.1, maximum=100)
    inverter_output_resistance: float = parameter(5.0, "ohm/phase", "Effective converter/output resistance used for current control and conduction loss", "estimated", minimum=1, maximum=100)
    inverter_idle_loss: float = parameter(3.0, "W", "Converter overhead when enabled above minimum DC voltage", "estimated", maximum=1000)
    inverter_min_dc_voltage: float = parameter(50.0, "V DC", "Below this voltage the averaged exciter is disabled", "estimated", minimum=1, maximum=1000)

    def __post_init__(self):
        for item in fields(self):
            value = getattr(self, item.name)
            if not math.isfinite(value) or not item.metadata["minimum"] <= value <= item.metadata["maximum"]:
                raise ValueError(f"{item.name}: enter {item.metadata['minimum']} to {item.metadata['maximum']} {item.metadata['unit']}")
        if self.pole_pairs != int(self.pole_pairs):
            raise ValueError("pole_pairs must be an integer")
