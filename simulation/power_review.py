"""Reproducible component tables: python -m simulation.power_review."""
from pathlib import Path
from .external_model import ExternalLoweringModel, reviewed_parameters


def main():
    lines=['# Power-balance review', '', 'Positive storage rate means charging; all powers are W.', '']
    for mode in ('exciter','capacitor'):
        m=ExternalLoweringModel(reviewed_parameters(precharge_voltage=200 if mode=='capacitor' else 0,
                                                    initial_shaft_rpm=1600 if mode=='capacitor' else 0))
        m.excitation_mode=mode
        if mode=='capacitor':
            m.start_mode='precharged';m.startup_enabled=False;m.brake_released=True
        m.reset()
        for target in (0,.05,.5,1.,3.):
            while m.state.time<target-1e-9:m.step()
            r=m.readings();d=r['power_diagnostics']
            lines.extend([f'## {mode}, t = {target:.2f} s', '',
                f"Speed {60*r['velocity']:.3f} m/min; cumulative residual {r['energy_residual']:+.8f} J; KCL {abs(d['kcl']):.3e} A.", '',
                '| Component | In | Out | Heat | dE/dt | Residual |', '|---|---:|---:|---:|---:|---:|'])
            for name,c in d['components'].items():
                lines.append('| '+name+' | '+' | '.join(f'{c[key]:.6f}' for key in ('input','output','heat','storage_rate','residual'))+' |')
            lines.append('')
    report='\n'.join(lines)
    Path('docs/power-balance-results.md').write_text(report,encoding='utf-8')
    print(report)


if __name__=='__main__':main()
