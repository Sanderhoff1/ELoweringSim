"""RK4 electrical-step convergence study; does not change production defaults."""
from __future__ import annotations
import json
from pathlib import Path
import time

from .performance_benchmark import build_case


FIELDS=('velocity','rpm','bus_frequency','line_voltage','machine_line_current',
        'flux_magnitude','motor_torque','dc_voltage','dc_brake_power')


def run(mode,maximum_step,duration,integrator_order=4):
    model,_=build_case(mode)
    model.max_electrical_step=maximum_step
    model.integrator_order=integrator_order
    peaks={key:0.0 for key in FIELDS};events=[];previous=model.sequence.name
    started=time.perf_counter();next_sample=0.0
    while model.state.time<duration-1e-12:
        model.step(min(.002,duration-model.state.time))
        if model.sequence.name!=previous:
            events.append((model.sequence.name,model.state.time));previous=model.sequence.name
        if model.state.time>=next_sample-1e-12:
            reading=model.readings();next_sample+=.01
            for key in FIELDS:peaks[key]=max(peaks[key],abs(reading[key]))
    wall=time.perf_counter()-started;final=model.readings()
    return dict(mode=mode,integrator=f'RK{integrator_order}',maximum_step_s=maximum_step,simulated_seconds=model.state.time,
                wall_seconds=wall,real_time_factor=model.state.time/wall,
                rejected_steps=model.rejected_steps,peaks=peaks,
                final={key:final[key] for key in FIELDS},events=events,
                energy_residual=final['energy_residual'],fault=final['fault'])


def differences(reference,candidate):
    def relative(a,b):return abs(b-a)/max(abs(a),1e-9)
    return dict(peak_relative={key:relative(reference['peaks'][key],candidate['peaks'][key]) for key in FIELDS},
                final_relative={key:relative(reference['final'][key],candidate['final'][key]) for key in FIELDS},
                maximum_event_shift_s=max((abs(b[1]-a[1]) for a,b in zip(reference['events'],candidate['events'])
                                           if a[0]==b[0]),default=0.0),
                energy_residual_change=candidate['energy_residual']-reference['energy_residual'])


def main():
    results=[]
    for mode,duration,steps in (
        ('canonical-exciter',4.0,(.00005,.0001,.0002,.0004)),
        ('capacitor-only',2.0,(.00002,.00005,.0001,.0002))):
        group=[]
        for step in steps:
            print(f'{mode}: max electrical step {step:g} s',flush=True)
            group.append(run(mode,step,duration))
        reference=next(row for row in group if row['maximum_step_s']==.0001)
        for row in group:row['difference_from_0_1ms']=differences(reference,row)
        results.extend(group)
    root=Path(__file__).resolve().parents[1]/'docs'/'performance'
    (root/'timestep-study.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    lines=['# RK4 electrical-timestep convergence','',
           '| Mode | Maximum step [ms] | Wall [s] | RTF | Rejected | Max peak difference | Max final difference | Event shift [ms] | Energy residual [J] |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in results:
        diff=row['difference_from_0_1ms']
        lines.append(f"| {row['mode']} | {1000*row['maximum_step_s']:.3f} | {row['wall_seconds']:.3f} | {row['real_time_factor']:.4f} | {row['rejected_steps']} | {100*max(diff['peak_relative'].values()):.4f}% | {100*max(diff['final_relative'].values()):.4f}% | {1000*diff['maximum_event_shift_s']:.3f} | {row['energy_residual']:+.8f} |")
    lines.extend(['','The production default remains 0.1 ms unless a larger candidate meets all engineering tolerances in both full reference runs.'])
    (root/'timestep-study.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def integrator_main():
    root=Path(__file__).resolve().parents[1]/'docs'/'performance'
    reference=json.loads((root/'timestep-study.json').read_text(encoding='utf-8'))
    reference=next(row for row in reference if row['mode']=='canonical-exciter'
                   and row['maximum_step_s']==.0001)
    results=[]
    for step in (.00005,.0001):
        print(f'RK2 canonical-exciter: {step:g} s',flush=True)
        row=run('canonical-exciter',step,4.0,2)
        row['difference_from_rk4_0_1ms']=differences(reference,row)
        results.append(row)
    (root/'integrator-study.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    lines=['# Integrator benchmark','',
           '| Integrator | Maximum step [ms] | Wall [s] | RTF | Rejected | Max peak difference | Max final difference | Event shift [ms] | Energy residual [J] |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    lines.append(f"| RK4 | 0.100 | {reference['wall_seconds']:.3f} | {reference['real_time_factor']:.4f} | {reference['rejected_steps']} | reference | reference | 0.000 | {reference['energy_residual']:+.8f} |")
    for row in results:
        diff=row['difference_from_rk4_0_1ms']
        lines.append(f"| RK2 | {1000*row['maximum_step_s']:.3f} | {row['wall_seconds']:.3f} | {row['real_time_factor']:.4f} | {row['rejected_steps']} | {100*max(diff['peak_relative'].values()):.4f}% | {100*max(diff['final_relative'].values()):.4f}% | {1000*diff['maximum_event_shift_s']:.3f} | {row['energy_residual']:+.8f} |")
    lines.extend(['','Adaptive explicit and semi-implicit replacements were not implemented: discontinuous converter-limit regions and the existing local energy acceptance test make a speculative replacement higher risk than the measured RK4 timestep gain.'])
    (root/'integrator-study.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':
    import sys
    integrator_main() if len(sys.argv)>1 and sys.argv[1]=='integrators' else main()
