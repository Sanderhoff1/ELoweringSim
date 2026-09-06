"""Plain-language presentation derived from model readings, never fed to physics."""
import math


def energy_budget(model, r):
    """Absolute energy inventory, with net external input shown separately.

    Energy cannot be assigned uniquely to gravity once sources mix. Never
    normalize losses to pretend they came exclusively from the falling load.
    """
    if not hasattr(model, 'initial_energy'):
        return None
    p = model.parameters
    potential = p.mass*p.gravity*p.crane_height
    source = r['source_energy']
    inputs = [('Initial height energy', potential),
              ('Initial motion / field / charge', model.initial_energy),
              ('Net external input', max(0, source))]
    outputs = [('Height remaining', potential+r['potential_energy']),
               ('Motion', r['kinetic_energy']),
               ('Field + capacitors', r['magnetic_energy']+r['capacitor_energy']),
               ('AC load heat', r['load_energy']),
               ('Winding heat', r['copper_energy']),
               ('Brake / friction / impact', model.mechanical_dissipation),
               ('Net returned externally', max(0, -source))]
    if r.get('rectifier_enabled'):
        outputs += [('DC capacitor', r['dc_energy']),
                    ('DC brake heat', r['dc_brake_energy']),
                    ('Bridge / source heat', r['rectifier_loss_energy'])]
    if r.get('dc_exciter'):
        outputs += [('Exciter heat',r['inverter_loss_energy'])]
    return dict(inputs=inputs, outputs=outputs, total=sum(x[1] for x in inputs),
                residual=r['energy_residual'], released=-r['potential_energy'])


def describe(model, readings, history):
    r, p, s = readings, model.parameters, model.state
    dynamic = 'flux_magnitude' in r
    voltage_reference = max(p.volts_per_hz*p.supply_frequency, 1.0)
    flux_reference = max(math.sqrt(2/3)*p.volts_per_hz/(2*math.pi), 0.001)
    field = r.get('flux_magnitude', flux_reference*r['line_voltage']/voltage_reference)
    field_ratio = field/flux_reference
    field_rate = 0.0
    if dynamic and history:
        earlier = next((row for row in reversed(history) if s.time-row[0]>=0.25), None)
        if earlier:
            field_rate = (field-earlier[14])/max(s.time-earlier[0], 1e-9)/flux_reference
    if not model.motor_connected:
        field_title = 'Machine disconnected'
    elif field_ratio < 0.02:
        field_title = 'Only a small magnetic seed' if field_ratio>0.0001 else 'No magnetic field yet'
    elif field_rate > 0.03:
        field_title = 'Magnetic field is building'
    elif field_rate < -0.03:
        field_title = 'Magnetic field is fading'
    else:
        field_title = 'Magnetic field is present'
    if s.grounded:
        motion = 'Load has reached the ground'
    elif abs(r['velocity']) < 0.005:
        motion = 'Load is stationary'
    elif r['velocity']*r['acceleration'] < -0.005:
        motion = 'Load is slowing down'
    elif r['velocity']*r['acceleration'] > 0.005:
        motion = 'Load is speeding up'
    else:
        motion = 'Load speed is nearly steady'
    if r['motor_torque']*r['omega'] < -0.1:
        torque_text = 'Machine opposes the motion'
    elif r['motor_torque']*r['omega'] > 0.1:
        torque_text = 'Machine helps drive the load'
    else:
        torque_text = 'Almost no electromagnetic work'
    if model.inverter_enabled:
        reason = 'Exciter connected: it can establish the field and exchange energy.'
        if r.get('dc_exciter'):
            reason = 'DC-fed exciter: '+r['inverter_status'].lower()+'. Its energy comes from the DC bus.'
    elif field_ratio >= 0.02:
        reason = 'Exciter OFF. The field still exists; watch whether it grows or fades.'
    elif r['line_voltage'] > 0.1:
        reason = 'Exciter OFF. Capacitor voltage is present, but little field has formed.'
    else:
        reason = 'Exciter OFF. A seed and suitable conditions are needed for voltage to build.'
    source_power = r['inverter_real_power'] if dynamic else -r['electrical_export']
    load_power = r.get('load_power', 0.0)
    cap_absorption = source_power+r['electrical_export']-load_power-r.get('rectifier_power',0) if dynamic else 0.0
    copper_power = r['rotor_loss']+r.get('stator_loss', 0)
    field_storage = r['electrical_input']-r['motor_shaft_power']-copper_power if dynamic else 0.0
    cap_reference_energy = 0.5*(3*p.capacitor_capacitance*1e-6)*voltage_reference**2
    cap_ratio = (r.get('capacitor_energy',0)/cap_reference_energy
                 if dynamic and cap_reference_energy else (r['line_voltage']/voltage_reference)**2)
    if not model.capacitors_enabled:
        cap_ratio = 0.0
    return dict(field_title=field_title, field_ratio=field_ratio, field_rate=field_rate,
                motion=motion, torque_text=torque_text, reason=reason,
                source_power=source_power, shaft_power=-r['motor_shaft_power'],
                terminal_export=r['electrical_export'], load_power=load_power,
                copper_power=copper_power, cap_absorption=cap_absorption,
                field_storage=field_storage, cap_ratio=cap_ratio,
                voltage_ratio=r['line_voltage']/p.motor_rated_voltage,
                dynamic=dynamic)
