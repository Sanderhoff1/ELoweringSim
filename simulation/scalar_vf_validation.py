"""Independent scalar-V/f operating-point and transition validation."""
from __future__ import annotations

import cmath
from csv import DictWriter
import math
from pathlib import Path

from .automatic_sequence import FIELDS
from .capacitor_rectifier import transfer
from .equivalent_circuit import operating_point
from .external_model import ExternalLoweringModel, reviewed_parameters
from .scalar_vf import base_flux, base_voltage, stator_drop_compensation


FREQUENCIES = (20.0, 15.0, 10.0, 7.5, 5.0)
DIAGNOSTIC_FIELDS = FIELDS


def _at_flux(p, frequency, slip):
    lo, hi = 0.0, p.motor_rated_voltage*1.5
    for _ in range(55):
        voltage = (lo+hi)/2
        point = operating_point(p, slip, voltage, frequency)
        if point['flux'] < base_flux(p):
            lo = voltage
        else:
            hi = voltage
    return (lo+hi)/2, operating_point(p, slip, (lo+hi)/2, frequency)


def theoretical_equilibrium(p, frequency):
    """Machine/load equilibrium at target flux before applying the DC network."""
    def residual(slip):
        voltage, point = _at_flux(p, frequency, slip)
        omega=(1-slip)*2*math.pi*frequency/p.pole_pairs
        # Released-brake mechanical equilibrium, including the same losses as
        # MechanicalModel._drive and its viscous term.
        required=-(p.mass*p.gravity*p.radius
                   -(1-p.gearbox_efficiency)*p.mass*p.gravity*p.radius
                   -p.drivetrain_loss_torque-p.damping*omega)
        return point['torque']-required, voltage, point, omega, required

    previous=(-1e-4,residual(-1e-4))
    bracket=None
    for index in range(1,1001):
        slip=-.002*index
        current=residual(slip)
        if current[0]*previous[1][0] <= 0:
            bracket=(previous[0],slip)
            break
        previous=(slip,current)
    if bracket is None:
        return None
    lo,hi=bracket
    for _ in range(50):
        mid=(lo+hi)/2
        if residual(lo)[0]*residual(mid)[0] <= 0: hi=mid
        else: lo=mid
    slip=(lo+hi)/2
    _,voltage,point,omega,required=residual(slip)
    return dict(frequency=frequency,slip=slip,line_voltage=voltage,
                omega=omega,rpm=omega*60/(2*math.pi),
                synchronous_rpm=60*frequency/p.pole_pairs,
                required_torque=required,**point)


def _phasor_state(p, equilibrium):
    frequency=equilibrium['frequency']; slip=equilibrium['slip']
    w=2*math.pi*frequency
    v=equilibrium['line_voltage']/math.sqrt(3)
    zs=complex(p.stator_resistance,w*p.stator_leakage)
    yr=1/complex(p.rotor_resistance/slip,w*p.rotor_leakage)
    lo,hi=1e-12,p.magnetizing_inductance
    for _ in range(70):
        lm=(lo+hi)/2
        em=v/(1+zs*(1/(1j*w*lm)+yr))
        flux=math.sqrt(2)*abs(em)/w
        target=p.magnetizing_inductance/(1+(flux/p.saturation_flux)**2)
        if lm<target:lo=lm
        else:hi=lm
    em=v/(1+zs*(1/(1j*w*lm)+yr))
    rotor=em*yr
    winding=(v-em)/zs
    pm=math.sqrt(2)*em/(1j*w)
    return (pm+p.stator_leakage*math.sqrt(2)*winding,
            pm-p.rotor_leakage*math.sqrt(2)*rotor,
            complex(math.sqrt(2)*v),pm,math.sqrt(2)*winding)


def initialized_case(frequency, seconds=1.0, sample_interval=.01):
    p=reviewed_parameters(supply_frequency=frequency,initial_shaft_rpm=0)
    equilibrium=theoretical_equilibrium(p,frequency)
    if equilibrium is None:
        return None,[],None
    model=ExternalLoweringModel(p)
    model.startup_enabled=False
    model.controls.speed_request_hz=frequency
    model.controls.main_bypass_command=True
    model.reset()
    ps,pr,voltage,pm,winding=_phasor_state(p,equilibrium)
    model.electrical.stator_flux=ps
    model.electrical.rotor_flux=pr
    model.electrical.voltage=voltage
    model.electrical.phase=cmath.phase(pm)
    model.electrical.aux_energy=.5*model.electrical.aux_capacitance*p.boost_target_voltage**2
    # Select the DC voltage that initially accepts the theoretical exported
    # power. The capacitor may subsequently charge because the chopper threshold
    # is intentionally left at the real configured value.
    lo,hi=0.0,math.sqrt(2)*equilibrium['line_voltage']
    for _ in range(60):
        rectified=(lo+hi)/2
        dc_power=transfer(equilibrium['line_voltage'],rectified,
                          p.rectifier_resistance)[1]
        if dc_power>-equilibrium['real_power']:lo=rectified
        else:hi=rectified
    rectified=(lo+hi)/2
    model.electrical.dc_energy=.5*model.kernel.cdc*rectified**2
    model.state.omega=equilibrium['omega']
    model.state.brake_fraction=0.0
    model.state.brake_command_released=True
    model.state.brake_motion_target=0.0
    model.brake_released=True
    model.release_time=0.0
    model.vf.frequency_command=frequency
    model.vf.flux_target=base_flux(p)
    rs=stator_drop_compensation(p,winding,pm,model.electrical.phase)
    commanded=1j*2*math.pi*frequency*ps+p.stator_resistance*winding
    source=commanded+p.inverter_output_resistance*winding
    source_line_rms=math.sqrt(3/2)*abs(source)
    desired=source_line_rms-base_voltage(p,frequency)-rs
    model.vf.flux_integral=desired/max(p.vf_flux_ki,1e-12)
    model.vf.base_voltage_command=base_voltage(p,frequency)
    model.vf.resistive_compensation=rs
    model.vf.flux_correction=desired
    model.vf.unlimited_voltage_command=source_line_rms
    model.vf.voltage_command=source_line_rms
    model.switchgear.k_precharge=False
    model.switchgear.k_main=True
    model.initial_energy=model.total_energy()
    rows=[]; sample_steps=max(1,round(sample_interval/.002))
    for index in range(round(seconds/.002)+1):
        if index%sample_steps==0:
            reading=model.readings()
            row={key:reading[key] for key in DIAGNOSTIC_FIELDS if key!='time'}
            row['time']=model.state.time;rows.append(row)
        if index<round(seconds/.002):model.step(.002)
    return model,rows,equilibrium


def transition_run(seconds_limit=20.0):
    model=ExternalLoweringModel(reviewed_parameters())
    model.controls.speed_request_hz=20.0
    model.reset()
    rows=[]; targets=list(FREQUENCIES); target_index=0;at_target=0.0
    count=round(seconds_limit/.002)
    for index in range(count+1):
        if index%5==0:
            r=model.readings();row={key:r[key] for key in DIAGNOSTIC_FIELDS if key!='time'}
            row['time']=model.state.time;rows.append(row)
        if model.sequence.name=='LOWERING' and not model.controls.stop:
            target=targets[target_index]
            model.controls.speed_request_hz=target
            if abs(model.vf.frequency_command-target)<=.05:
                at_target+=.002
                if at_target>=.4 and target_index<len(targets)-1:
                    target_index+=1;at_target=0.0
                elif at_target>=.4:
                    model.controls.stop=True
            else:at_target=0.0
        if index<count:model.step(.002)
        if model.sequence.name in ('STOPPED','FAULT'):break
    return model,rows


def _stability(rows,frequency):
    final=rows[-1]
    tail=rows[max(0,len(rows)-20):]
    speed_change=abs(tail[-1]['rpm']-tail[0]['rpm'])
    frequency_error=abs(final['bus_frequency']-frequency)
    stable=(not final['fault'] and speed_change<5.0 and
            frequency_error<max(.5,.05*frequency))
    return stable,speed_change,frequency_error


def write_reports(root=None):
    root=Path(__file__).resolve().parents[1] if root is None else Path(root)
    docs=root/'docs';summary=[]
    for frequency in FREQUENCIES:
        model,rows,equilibrium=initialized_case(frequency)
        final=rows[-1];stable,speed_change,frequency_error=_stability(rows,frequency)
        summary.append((frequency,model,rows,equilibrium,final,stable,speed_change,frequency_error))
    columns=('target_hz','stable','load_speed_m_min','rotor_rpm','synchronous_rpm','slip',
             'v_ll_rms','current_rms','active_current','reactive_current','flux_target','actual_flux',
             'copper_loss_w','core_loss_w','mechanical_input_w','electrical_export_w','dc_link_power_w',
             'resistor_power_w','exciter_active_w','exciter_reactive_var','actual_bus_frequency_hz',
             'speed_change_last_0_2_s_rpm','frequency_error_hz','fault')
    csv_rows=[]
    for f,model,rows,equilibrium,r,stable,ds,df in summary:
        csv_rows.append(dict(zip(columns,(f,stable,60*r['velocity'],r['rpm'],r['synchronous_rpm'],r['slip'],
            r['line_voltage'],r['machine_line_current'],r['machine_active_current'],r['machine_reactive_current'],
            r['flux_target'],r['flux_magnitude'],r['machine_copper_loss'],r['machine_core_loss'],
            -r['motor_shaft_power'],r['electrical_export'],r['dc_input_power'],r['dc_brake_power'],
            r['inverter_real_power'],r['inverter_reactive_supply'],r['bus_frequency'],ds,df,r['fault']))))
    with (docs/'scalar-vf-steady-points.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=DictWriter(stream,fieldnames=columns);writer.writeheader();writer.writerows(csv_rows)
    lines=['# Scalar V/f independently initialized operating points','',
           'Each case starts from the nonlinear T-circuit machine/load torque equilibrium at the requested peak magnetizing-flux target, with the common rectifier/DC plant then integrated dynamically. `Stable` requires both speed settling and actual AC frequency tracking; a command value alone does not qualify.','',
           '| Command | Stable | Speed [m/min] | Rotor [rpm] | Actual / command f [Hz] | Slip | V LL [V] | I [A] | Flux target / actual [Wb] | Cu / core [W] | Mechanical / export / DC / resistor [W] | Exciter P / Q |',
           '|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in csv_rows:
        lines.append(f"| {row['target_hz']:g} | {'yes' if row['stable'] else 'no'} | {row['load_speed_m_min']:.3f} | {row['rotor_rpm']:.1f} | {row['actual_bus_frequency_hz']:.2f} / {row['target_hz']:g} | {row['slip']:.3f} | {row['v_ll_rms']:.1f} | {row['current_rms']:.2f} | {row['flux_target']:.3f} / {row['actual_flux']:.3f} | {row['copper_loss_w']:.1f} / {row['core_loss_w']:.1f} | {row['mechanical_input_w']:.1f} / {row['electrical_export_w']:.1f} / {row['dc_link_power_w']:.1f} / {row['resistor_power_w']:.1f} | {row['exciter_active_w']:.1f} / {row['exciter_reactive_var']:.1f} |")
    lines.extend(['',
        'The isolated T-circuit calculation finds a machine torque equilibrium at every requested frequency, but that is not a stable equilibrium of the complete present architecture. At target flux the rectified crest is below the 500 V chopper threshold, so the DC capacitor charges without providing a continuous resistor load. Braking torque then collapses and rotor speed/frequency move away from the command. Lower frequencies additionally require increasing negative slip and convert a growing share of mechanical input into machine copper loss.',
        ''])
    (docs/'scalar-vf-steady-points.md').write_text('\n'.join(lines),encoding='utf-8')
    model,rows=transition_run()
    with (docs/'scalar-vf-transition.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=DictWriter(stream,fieldnames=DIAGNOSTIC_FIELDS);writer.writeheader();writer.writerows(rows)
    selected=[]
    for frequency in FREQUENCIES:
        candidates=[row for row in rows
                    if abs(row['stator_frequency_command']-frequency)<=.05
                    and row['sequence_state']=='LOWERING']
        selected.append((frequency,candidates[-1] if candidates else None))
    maximum_flux=max(row['flux_magnitude'] for row in rows)
    maximum_current=max(row['machine_line_current'] for row in rows)
    transition_lines=['# Scalar V/f 20 → 15 → 10 → 7.5 → 5 Hz transition','',
        'The companion CSV is sampled every 10 ms. It contains the requested command decomposition, flux error/integral, current/flux/voltage limit flags, actual bus frequency, active/reactive power, DC link, chopper, contactor, brake, controller-state, and fault telemetry. Targets below are command-settled samples; they are not called physical operating points unless actual bus frequency also follows.','',
        '| Command [Hz] | Actual bus [Hz] | Flux target / actual / max [Wb] | V base / Rs / PI / final [V LL RMS] | I [A RMS] | AC export / DC in / resistor [W] | Limit flags (I/F/V) | State / fault |',
        '|---:|---:|---:|---:|---:|---:|---|---|']
    for frequency,row in selected:
        if row is None:
            transition_lines.append(f'| {frequency:g} | not reached | - | - | - | - | - | - |')
            continue
        flags=f"{int(row['vf_current_limited'])}/{int(row['vf_flux_limited'])}/{int(row['vf_voltage_limited'])}"
        transition_lines.append(f"| {frequency:g} | {row['bus_frequency']:.2f} | {row['flux_target']:.3f} / {row['flux_magnitude']:.3f} / {row['maximum_flux']:.3f} | {row['vf_base_voltage']:.1f} / {row['vf_resistive_compensation']:.1f} / {row['vf_flux_correction']:.1f} / {row['voltage_command']:.1f} | {row['machine_line_current']:.2f} | {row['electrical_export']:.1f} / {row['dc_input_power']:.1f} / {row['dc_brake_power']:.1f} | {flags} | {row['sequence_state']} / {row['fault'] or 'NONE'} |")
    transition_lines.extend(['',
        f'Maximum recorded flux/current: {maximum_flux:.3f} Wb-turn / {maximum_current:.3f} A RMS. Final state: `{model.sequence.name}`; fault: `{model.switchgear.fault or "NONE"}`.', '',
        'Interpretation: compare the actual-bus and command columns before judging a target viable. In the retained architecture the flux loop can remain controlled while the generating rotor and passive rectifier/DC load determine a much higher actual electrical frequency. That is a plant/control-authority limitation, not a hidden relabeling of command frequency.', ''])
    (docs/'scalar-vf-transition.md').write_text('\n'.join(transition_lines),encoding='utf-8')
    return model,rows,csv_rows


if __name__=='__main__':
    model,rows,points=write_reports()
    print(f'wrote {len(points)} steady cases and {len(rows)} transition samples; final={model.sequence.name}, fault={model.switchgear.fault or "NONE"}')
