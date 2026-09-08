"""Finite constant-OCV battery and isolated averaged converter power paths.

Positive current discharges: Vt=Voc-RI, Pterminal=Vt I,
chemical depletion=Voc I=Pterminal+R I². No SOC/energy clipping.
"""
import math


def discharge_limit(p, energy=float('inf'), h=1e-4):
    i=min(p.battery_discharge_current_limit, energy/(h*p.battery_voltage))
    if p.battery_internal_resistance:
        i=min(i,p.battery_voltage/(2*p.battery_internal_resistance))
    return (p.battery_voltage-p.battery_internal_resistance*i)*i


def boost_limit(p, energy=float('inf'), h=1e-4):
    return min(discharge_limit(p,energy,h)*p.boost_efficiency,
               p.boost_input_power_limit*p.boost_efficiency,
               p.boost_target_voltage*p.boost_output_current_limit)


def battery(p, terminal_power):
    v,r=p.battery_voltage,p.battery_internal_resistance
    i=2*terminal_power/(v+math.sqrt(max(0,v*v-4*r*terminal_power)))
    return v-r*i,i,r*i*i


def paths(p, energy, supply, vdc, h, charger_enabled=True):
    draw=supply/p.boost_efficiency
    room=max(0,p.battery_capacity_wh*3600-energy)
    charge_i=min(p.battery_charge_current_limit,room/(h*p.battery_voltage))
    max_charge=(p.battery_voltage+p.battery_internal_resistance*charge_i)*charge_i
    cin=min(p.charger_power_limit,(draw+max_charge)/p.charger_efficiency) if charger_enabled and vdc>=p.charger_min_dc_voltage else 0.
    cout=cin*p.charger_efficiency
    vt,i,heat=battery(p,draw-cout)
    return dict(boost_input=draw,boost_output=supply,boost_heat=draw-supply,
                charger_input=cin,charger_output=cout,charger_heat=cin-cout,
                voltage=vt,current=i,power=vt*i,heat=heat,storage=-p.battery_voltage*i)
