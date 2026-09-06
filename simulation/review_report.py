"""Reproduce reviewed-topology measurements: python -m simulation.review_report."""
import json
from pathlib import Path
import time
from .external_model import ExternalLoweringModel, reviewed_parameters
from .dynamic_model import DynamicLoweringModel
from .examples import small_hoist
from .equivalent_circuit import operating_point
from .validation import dynamic_operating_point, CASES


def timed_run(model,seconds):
    start=time.perf_counter()
    for _ in range(round(seconds/.002)):
        model.step(.002)
    return time.perf_counter()-start,model.readings()


def main():
    old=DynamicLoweringModel(small_hoist(initial_shaft_rpm=1530,initial_flux=0,dc_initial_voltage=600))
    old.rectifier_enabled=old.chopper_active=old.dc_exciter=True
    old.brake_released=True
    old.reset()
    wall,legacy=timed_run(old,1)
    baseline=dict(omega=162.6989516219423,position=.272515344981704,dc_voltage=589.3650835642283,
                  motor_torque=-4.74230105502952,electrical_export=672.162446544828,
                  rectifier_power=0,dc_brake_power=653.8459657170382,energy_residual=6.690376324058889e-7)
    report=dict(legacy_same_physics=dict(before_wall_seconds=3.4853258999064565,after_wall_seconds=wall,
        simulation_seconds=1,before=baseline,after={k:legacy[k] for k in baseline},
        max_absolute_difference=max(abs(legacy[k]-v) for k,v in baseline.items())))
    m=ExternalLoweringModel()
    wall,r=timed_run(m,3)
    report['reviewed_startup']=dict(wall_seconds=wall,simulation_seconds=3,release_time=m.release_time,readings=r)
    report['convergence']=[]
    for h in (4e-5,2e-5,1e-5):
        model=ExternalLoweringModel()
        model.max_electrical_step=h
        _,r=timed_run(model,1.2)
        report['convergence'].append(dict(max_electrical_step=h,**{k:r[k] for k in ('velocity','dc_voltage','flux_magnitude','energy_residual')}))
    report['equivalent_circuit']=[]
    p=reviewed_parameters()
    dynamic_time=steady_time=0
    for slip,voltage in CASES:
        start=time.perf_counter()
        reference=operating_point(p,slip,voltage)
        steady_time+=time.perf_counter()-start
        start=time.perf_counter()
        measured=dynamic_operating_point(p,slip,voltage)
        dynamic_time+=time.perf_counter()-start
        report['equivalent_circuit'].append(dict(slip=slip,line_voltage=voltage,reference=reference,
            dynamic=measured,absolute_errors={k:abs(v-reference[k]) for k,v in measured.items()}))
    report['prescribed_operating_point_runtime']=dict(dynamic_seconds=dynamic_time,quasi_steady_seconds=steady_time,cases=len(CASES),
        limitation='T-circuit sweeps prescribe voltage and speed; not a coupled startup or autonomous self-excitation solver.')
    target=Path(__file__).resolve().parents[1]/'docs'/'review-results.json'
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('Saved',target)
    print('Same-physics runtime:',report['legacy_same_physics'])
    print('Reviewed startup:',report['reviewed_startup']['wall_seconds'],'wall seconds; release at',m.release_time)
    print('Operating point runtime:',report['prescribed_operating_point_runtime'])


if __name__=='__main__':
    main()
