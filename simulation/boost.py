"""Power-limited averaged 24 V support source; no switching or battery chemistry."""


def support(p, voltage, current_state, enabled):
    voltage=max(0.0,float(voltage.real))
    current_state=max(0.0,float(current_state.real))
    available=min(p.boost_output_current_limit,
                  p.boost_efficiency*p.boost_input_power_limit/max(voltage,p.battery_voltage))
    demand=min(available,max(0.0,(p.boost_target_voltage-voltage)*p.boost_voltage_gain))
    command=demand if enabled else 0.0
    derivative=(command-current_state)/p.boost_response
    # Output isolation blocks reverse flow and stops injection at/above target.
    current=min(current_state,available) if enabled and voltage<p.boost_target_voltage else 0.0
    output=voltage*current
    battery=output/p.boost_efficiency
    status=('OFF' if not enabled else 'STANDBY' if voltage>=p.boost_target_voltage-0.5 and current<0.01
            else ('CURRENT LIMITED' if available>=p.boost_output_current_limit else 'POWER LIMITED')
            if demand>=available-1e-8 and available>0 else 'SUPPORTING')
    return dict(current=current,derivative=derivative,output_power=output,
                battery_power=battery,battery_current=battery/p.battery_voltage,
                loss=battery-output,status=status)
