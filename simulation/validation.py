"""Prescribed-voltage dynamic measurement, independent of the T-circuit solve."""
import cmath
import math
from .external_model import Kernel


CASES=((1,100),(.2,200),(.03,400),(0,400),(-.02,200),(-.04,400),(-.1,350),(-.3,150))


def dynamic_operating_point(p,slip,line_voltage,seconds=2.0,h=1e-4):
    k=Kernel(p)
    w=2*math.pi*p.supply_frequency
    omega=(1-slip)*w/p.pole_pairs
    peak=math.sqrt(2/3)*line_voltage
    ps=pr=0j
    count=round(seconds/h)
    for j in range(count):
        t=j*h
        def derivative(a,b,offset):
            return k.winding_rates(a,b,peak*cmath.exp(1j*w*(t+offset)),omega)
        a=derivative(ps,pr,0)
        b=derivative(ps+h*a[0]/2,pr+h*a[1]/2,h/2)
        c=derivative(ps+h*b[0]/2,pr+h*b[1]/2,h/2)
        d=derivative(ps+h*c[0],pr+h*c[1],h)
        ps+=h*(a[0]+2*b[0]+2*c[0]+d[0])/6
        pr+=h*(a[1]+2*b[1]+2*c[1]+d[1])/6
    v=peak*cmath.exp(1j*w*count*h)
    is_=k.currents(ps,pr)[0]+v/p.core_loss_resistance
    power=1.5*v*is_.conjugate()
    return dict(torque=k.torque(ps,pr),current=abs(is_)/math.sqrt(2),
                real_power=power.real,reactive_power=power.imag)
