"""Run and plot the architecture-valid 300 kg startup demonstration."""
from csv import DictWriter
from pathlib import Path

from .external_model import ExternalLoweringModel


SAMPLE_FIELDS=(
    'time','startup_status','main_dc_connection','brake_command','brake_physical_state',
    'velocity','rpm','bus_frequency','line_voltage','aux_voltage','dc_voltage',
    'flux_magnitude','battery_voltage','battery_current','battery_power',
    'boost_input_power','boost_power','inverter_dc_power','inverter_real_power',
    'inverter_reactive_supply','inverter_current','electrical_export','rectifier_power',
    'dc_input_power','dc_capacitor_power','dc_brake_power','charger_input_power',
    'energy_residual','exciter_solver_status','k_cap','k_exc','k_precharge','k_main')


def run(seconds=3.0):
    model=ExternalLoweringModel()
    rows=[]
    for index in range(round(seconds/.002)+1):
        if index%5==0:
            reading=model.readings()
            reading['time']=model.state.time
            rows.append({key:reading[key] for key in SAMPLE_FIELDS})
        if index<round(seconds/.002): model.step(.002)
    return model,rows


def first(rows,predicate):
    return next((row for row in rows if predicate(row)),None)


def svg(rows,path):
    width,height=1200,760
    left,right,top=85,1165,50
    panel_h=180
    duration=rows[-1]['time']
    panels=[
        ('Voltage [V]',(('Aux HV','aux_voltage','#48d6b0'),('AC line RMS','line_voltage','#a78bfa'),('Main DC','dc_voltage','#ffbd66'))),
        ('Motion / frequency',(('Lowering [m/min]','velocity','#ffbd66',60),('Field [Hz]','bus_frequency','#60a5fa',1))),
        ('Real power [W]',(('Battery terminal','battery_power','#60a5fa'),('Inverter AC','inverter_real_power','#a78bfa'),('Machine export','electrical_export','#48d6b0'),('Rectifier AC','rectifier_power','#f59e0b'),('Resistor','dc_brake_power','#fb7185'),('Charger input','charger_input_power','#22d3ee'))),
    ]
    def x(t):return left+(right-left)*t/duration
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
         '<rect width="100%" height="100%" fill="#0f1b2d"/>',
         '<style>text{font-family:Segoe UI,Arial;fill:#dce8f5}.muted{fill:#93a4b8;font-size:12px}.title{font-size:18px;font-weight:600}</style>',
         '<text x="85" y="27" class="title">300 kg architecture startup: averaged dynamic model</text>']
    for panel,(title,traces) in enumerate(panels):
        y0=top+panel*230
        values=[]
        for trace in traces:
            scale=trace[3] if len(trace)>3 else 1
            values.extend(row[trace[1]]*scale for row in rows)
        lo=min(0,min(values));hi=max(values)
        if hi-lo<1e-9:hi=lo+1
        def y(value):return y0+panel_h-(value-lo)/(hi-lo)*panel_h
        out.append(f'<rect x="{left}" y="{y0}" width="{right-left}" height="{panel_h}" fill="#13243a" stroke="#354b65"/>')
        out.append(f'<text x="{left}" y="{y0-10}" class="title">{title}</text>')
        out.append(f'<text x="{left-8}" y="{y0+8}" text-anchor="end" class="muted">{hi:.0f}</text>')
        out.append(f'<text x="{left-8}" y="{y0+panel_h}" text-anchor="end" class="muted">{lo:.0f}</text>')
        for trace in traces:
            label,key,color,*rest=trace;scale=rest[0] if rest else 1
            points=' '.join(f'{x(row["time"]):.2f},{y(row[key]*scale):.2f}' for row in rows)
            out.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
        legend_x=left
        for trace in traces:
            label,key,color,*_=trace
            out.append(f'<line x1="{legend_x}" y1="{y0+panel_h+18}" x2="{legend_x+18}" y2="{y0+panel_h+18}" stroke="{color}" stroke-width="3"/>')
            out.append(f'<text x="{legend_x+23}" y="{y0+panel_h+22}" class="muted">{label}</text>')
            legend_x+=max(115,9*len(label))
    for second in range(int(duration)+1):
        out.append(f'<text x="{x(second):.1f}" y="748" text-anchor="middle" class="muted">{second} s</text>')
    out.append('</svg>')
    path.write_text('\n'.join(out)+'\n',encoding='utf-8')


def main():
    root=Path(__file__).resolve().parents[1]
    docs=root/'docs'
    model,rows=run()
    csv_path=docs/'architecture-demo.csv'
    with csv_path.open('w',newline='',encoding='utf-8') as handle:
        writer=DictWriter(handle,fieldnames=SAMPLE_FIELDS);writer.writeheader();writer.writerows(rows)
    svg_path=docs/'architecture-demo.svg';svg(rows,svg_path)
    milestones=[
        ('Auxiliary HV ready',lambda r:r['aux_voltage']>=model.parameters.aux_ready_voltage),
        ('Field ready',lambda r:r['flux_magnitude']>=model.parameters.startup_flux_fraction*model.parameters.exciter_flux_target),
        ('Brake release commanded',lambda r:r['brake_command']=='RELEASE'),
        ('Brake physically released',lambda r:r['brake_physical_state']=='RELEASED'),
        ('Generating terminal power',lambda r:r['electrical_export']>1),
        ('Main-link precharge',lambda r:r['main_dc_connection']=='PRECHARGE'),
        ('Main contactor closed',lambda r:r['main_dc_connection']=='MAIN'),
        ('Chopper active',lambda r:r['dc_brake_power']>1),
        ('Battery charger active',lambda r:r['charger_input_power']>1),
    ]
    lines=['# Architecture startup demonstration','',
           'Generated by `python -m simulation.architecture_demo` from the physics telemetry.','',
           '## Sequence','', '| Event | First time [s] |','|---|---:|']
    events=[(row['time'] if row else float('inf'),label,row)
            for label,predicate in milestones for row in [first(rows,predicate)]]
    for _,label,row in sorted(events):
        lines.append(f'| {label} | {row["time"]:.3f} |' if row else f'| {label} | not reached |')
    peak_fields=('battery_current','boost_input_power','aux_voltage','inverter_current',
                 'inverter_real_power','inverter_reactive_supply','rectifier_power',
                 'dc_voltage','dc_capacitor_power','dc_brake_power','charger_input_power')
    lines.extend(['','## Peak absolute sizing signals','', '| Signal | Peak |','|---|---:|'])
    for key in peak_fields:
        lines.append(f'| `{key}` | {max(abs(row[key]) for row in rows):.6g} |')
    final=rows[-1]
    lines.extend(['','## Final 3 s state','',
        f'- Lowering speed: {60*final["velocity"]:.3f} m/min',
        f'- AC / auxiliary / main DC voltage: {final["line_voltage"]:.2f} / {final["aux_voltage"]:.2f} / {final["dc_voltage"]:.2f} V',
        f'- Machine export / rectifier / resistor: {final["electrical_export"]:.2f} / {final["rectifier_power"]:.2f} / {final["dc_brake_power"]:.2f} W',
        f'- Whole-system energy residual: {final["energy_residual"]:+.8f} J','',
        '- [Time history CSV](architecture-demo.csv)',
        '- [Startup plot](architecture-demo.svg)',''])
    report=docs/'architecture-demo.md';report.write_text('\n'.join(lines),encoding='utf-8')
    print('\n'.join(lines))
    print(f'\nSaved {csv_path}\nSaved {svg_path}\nSaved {report}')


if __name__=='__main__':main()
