"""Independent nonlinear per-phase T circuit; RMS phasors, positive motoring.

Fast prescribed-speed/voltage operating points for sweeps, not a startup solver.
No dynamic kernel or current inversion is used in this reference calculation.
"""
import math


def operating_point(p, slip, line_voltage, frequency=None):
    frequency=p.supply_frequency if frequency is None else frequency
    if frequency<=0 or line_voltage<0:
        raise ValueError('Positive frequency and nonnegative RMS voltage required')
    w=2*math.pi*frequency
    v=line_voltage/math.sqrt(3)
    zs=complex(p.stator_resistance,w*p.stator_leakage)
    yr=0j if slip==0 else 1/complex(p.rotor_resistance/slip,w*p.rotor_leakage)
    def solve(lm):
        ym=1/(1j*w*lm)
        em=v/(1+zs*(ym+yr))
        flux=math.sqrt(2)*abs(em)/w
        return em,flux
    # Solve the saturation law independently in inductance, not flux/current.
    lo,hi=1e-12,p.magnetizing_inductance
    for _ in range(70):
        lm=(lo+hi)/2
        em,flux=solve(lm)
        target=p.magnetizing_inductance/(1+(flux/p.saturation_flux)**2)
        if lm<target: lo=lm
        else: hi=lm
    em,flux=solve(lm)
    ir=em*yr
    winding=(v-em)/zs
    current=winding+v/p.core_loss_resistance
    power=3*v*current.conjugate()
    torque=0.0 if slip==0 else 3*abs(ir)**2*p.rotor_resistance/slip/(w/p.pole_pairs)
    return dict(torque=torque,current=abs(current),real_power=power.real,
                reactive_power=power.imag,flux=flux,core_loss=3*v*v/p.core_loss_resistance,
                copper_loss=3*(p.stator_resistance*abs(winding)**2+p.rotor_resistance*abs(ir)**2))
