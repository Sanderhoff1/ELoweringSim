"""Deterministic performance/reference harness for the reviewed plant.

Instrumentation is installed only while this module runs.  It intentionally
keeps the production numerical path free of timers and counters.
"""
from __future__ import annotations

from contextlib import ExitStack
from csv import DictWriter
from dataclasses import dataclass, field
import json
from pathlib import Path
import statistics
import time
from unittest.mock import patch

from . import external_model as plant
from . import power_diagnostics
from .external_model import ExternalLoweringModel, reviewed_parameters
from .replay_io import ReplayFrame, ReplayState


REFERENCE_FIELDS = (
    'time','sequence_state','velocity','rpm','bus_frequency','slip','line_voltage',
    'machine_line_current','machine_active_current','machine_reactive_current',
    'flux_magnitude','motor_torque','motor_shaft_power','electrical_export',
    'machine_reactive_demand','machine_copper_loss','machine_core_loss',
    'magnetic_storage_power','rectifier_power','dc_input_power','dc_voltage',
    'dc_capacitor_power','chopper_target_voltage','chopper_duty','dc_brake_power',
    'battery_voltage','battery_power','aux_voltage','aux_power','energy_residual',
    'k_precharge','k_main','brake_command','brake_physical_state','fault')


@dataclass
class Counters:
    counts: dict = field(default_factory=dict)
    seconds: dict = field(default_factory=dict)
    solver_iterations: list = field(default_factory=list)

    def add(self,name,elapsed):
        self.counts[name]=self.counts.get(name,0)+1
        self.seconds[name]=self.seconds.get(name,0.0)+elapsed


def timed(counter,name,function,after=None):
    def wrapper(*args,**kwargs):
        started=time.perf_counter()
        result=function(*args,**kwargs)
        counter.add(name,time.perf_counter()-started)
        if after is not None:
            after(result)
        return result
    return wrapper


class Instrumentation:
    def __init__(self):
        self.counter=Counters()
        self.stack=ExitStack()

    def __enter__(self):
        c=self.counter
        solver_after=lambda result:c.solver_iterations.append(result[1])
        replacements=(
            (plant.Kernel,'rate',timed(c,'kernel_rate',plant.Kernel.rate)),
            (plant.Kernel,'currents',timed(c,'machine_currents',plant.Kernel.currents)),
            (plant,'_bounded_network_root',timed(c,'ac_bus_solver',plant._bounded_network_root,solver_after)),
            (plant,'transfer',timed(c,'rectifier',plant.transfer)),
            (plant,'midpoint_voltage',timed(c,'dc_link',plant.midpoint_voltage)),
            (plant,'chopper',timed(c,'chopper_controller',plant.chopper)),
            (plant,'scalar_vf_step',timed(c,'scalar_controller',plant.scalar_vf_step)),
            (ExternalLoweringModel,'_sequence',timed(c,'state_controller',ExternalLoweringModel._sequence)),
            (ExternalLoweringModel,'_substep',timed(c,'electrical_substep',ExternalLoweringModel._substep)),
            (ExternalLoweringModel,'readings',timed(c,'readings',ExternalLoweringModel.readings)),
            (power_diagnostics,'diagnostics',timed(c,'energy_diagnostics',power_diagnostics.diagnostics)),
        )
        for target,name,replacement in replacements:
            self.stack.enter_context(patch.object(target,name,replacement))
        return c

    def __exit__(self,*exc):
        self.stack.close()


def build_case(name):
    if name=='canonical-exciter':
        model=ExternalLoweringModel(reviewed_parameters())
        model.excitation_mode='exciter';model.start_mode='residual'
        model.controls.automatic_profile=True;duration=14.0
    elif name=='capacitor-only':
        model=ExternalLoweringModel(reviewed_parameters(initial_flux=.005))
        model.excitation_mode='capacitor';model.start_mode='residual'
        model.controls.automatic_profile=True;duration=8.0
    elif name=='fixed-exciter-20hz':
        model=ExternalLoweringModel(reviewed_parameters())
        model.excitation_mode='exciter';model.start_mode='residual'
        model.controls.speed_request_hz=20.0;duration=10.0
    else:
        raise ValueError(name)
    model.reset()
    return model,duration


def replay_frame(model,reading):
    s=model.state
    return ReplayFrame(s.time,reading,
        ReplayState(s.time,s.position,s.angle,s.omega,s.grounded,
                    s.impact_speed,s.impact_energy),
        model.brake_released,model.motor_connected,model.inverter_enabled,
        model.capacitors_enabled)


def run_case(name,reference_path):
    model,duration=build_case(name)
    rows=[];frames=[];outer_steps=0;integration_seconds=0.0
    sample_interval=.01;next_sample=0.0
    with Instrumentation() as counter:
        wall_started=time.perf_counter()
        while model.state.time<duration-1e-12:
            if model.state.time>=next_sample-1e-12:
                reading=model.readings()
                row={key:(model.state.time if key=='time' else reading[key])
                     for key in REFERENCE_FIELDS}
                rows.append(row)
                started=time.perf_counter();frames.append(replay_frame(model,reading))
                counter.add('replay_frame',time.perf_counter()-started)
                next_sample+=sample_interval
            started=time.perf_counter()
            model.step(min(.002,duration-model.state.time))
            integration_seconds+=time.perf_counter()-started
            outer_steps+=1
        reading=model.readings()
        row={key:(model.state.time if key=='time' else reading[key])
             for key in REFERENCE_FIELDS}
        rows.append(row)
        started=time.perf_counter();frames.append(replay_frame(model,reading))
        counter.add('replay_frame',time.perf_counter()-started)
        wall=time.perf_counter()-wall_started
    reference_path.parent.mkdir(parents=True,exist_ok=True)
    with reference_path.open('w',newline='',encoding='utf-8') as stream:
        writer=DictWriter(stream,fieldnames=REFERENCE_FIELDS)
        writer.writeheader();writer.writerows(rows)
    iterations=counter.solver_iterations
    return dict(case=name,simulated_seconds=model.state.time,wall_seconds=wall,
        real_time_factor=model.state.time/wall,outer_integration_steps=outer_steps,
        electrical_substep_calls=counter.counts.get('electrical_substep',0),
        derivative_evaluations=counter.counts.get('kernel_rate',0),
        algebraic_solves=counter.counts.get('ac_bus_solver',0),
        average_solver_iterations=statistics.mean(iterations) if iterations else 0.0,
        maximum_solver_iterations=max(iterations,default=0),telemetry_frames=len(frames),
        integration_wall_seconds=integration_seconds,counts=counter.counts,
        subsystem_seconds=counter.seconds,final_energy_residual=reading['energy_residual'],
        final_state=reading['sequence_state'],fault=reading['fault'])


def markdown(label,results):
    lines=[f'# Simulation performance {label}','',
           '| Case | Simulated [s] | Wall [s] | Real-time factor | Outer steps | Electrical substeps | Derivatives | AC solves | Solver iterations avg / max |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in results:
        lines.append(f"| {r['case']} | {r['simulated_seconds']:.3f} | {r['wall_seconds']:.3f} | {r['real_time_factor']:.4f} | {r['outer_integration_steps']} | {r['electrical_substep_calls']} | {r['derivative_evaluations']} | {r['algebraic_solves']} | {r['average_solver_iterations']:.3f} / {r['maximum_solver_iterations']} |")
    lines.extend(['','## Inclusive subsystem timings','',
                  'Timings overlap: for example AC-bus solver time is included in `Kernel.rate`, and both are included in integration time.','',
                  '| Case | Integration | Kernel.rate | Machine currents | AC solver | Rectifier | DC link | Controllers | Readings | Energy diagnostics | Replay frames |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|'])
    for r in results:
        s=r['subsystem_seconds'];controllers=sum(s.get(k,0) for k in ('scalar_controller','chopper_controller','state_controller'))
        lines.append(f"| {r['case']} | {r['integration_wall_seconds']:.3f} | {s.get('kernel_rate',0):.3f} | {s.get('machine_currents',0):.3f} | {s.get('ac_bus_solver',0):.3f} | {s.get('rectifier',0):.3f} | {s.get('dc_link',0):.3f} | {controllers:.3f} | {s.get('readings',0):.3f} | {s.get('energy_diagnostics',0):.3f} | {s.get('replay_frame',0):.6f} |")
    lines.extend(['','Reference histories are stored beside this report at 10 ms intervals.'])
    return '\n'.join(lines)+'\n'


def main(label='baseline',cases=None):
    root=Path(__file__).resolve().parents[1]
    output=root/'docs'/'performance'
    cases=tuple(cases or ('canonical-exciter','capacitor-only','fixed-exciter-20hz'))
    results=[]
    for name in cases:
        print(f'Benchmarking {label} {name}...',flush=True)
        results.append(run_case(name,output/f'{label}-{name}.csv'))
        print(json.dumps(results[-1],indent=2),flush=True)
    (output/f'{label}.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    (output/f'{label}.md').write_text(markdown(label,results),encoding='utf-8')


if __name__=='__main__':
    import sys
    if len(sys.argv)>1 and sys.argv[1]=='profile':
        import cProfile
        import pstats
        model,_=build_case(sys.argv[2])
        duration=float(sys.argv[3])
        profiler=cProfile.Profile();profiler.enable()
        while model.state.time<duration-1e-12:model.step(.002)
        profiler.disable();pstats.Stats(profiler).sort_stats('cumulative').print_stats(35)
    else:
        main(sys.argv[1] if len(sys.argv)>1 else 'baseline',sys.argv[2:])
