"""Responsive two-row energy diagram with reserved routing lanes."""
import math

GOLD, PURPLE, TEAL, HEAT = '#ffc36a', '#b7a2ff', '#60e0c1', '#ff977a'
WHITE, MUTED, BG = '#e5edf6', '#90a5bb', '#101b2c'


class EnergyView:
    def __init__(self, canvas, toggle_exciter):
        self.canvas = canvas

    def draw(self, model, r, history, playing):
        c = self.canvas
        c.delete('all')
        width, height = max(1, c.winfo_width()), max(1, c.winfo_height())
        c.configure(scrollregion=(0, 0, width, height))
        sx, sy = width / 960, height / 690
        font_scale = min(sx, sy)
        def xy(x, y):
            return x*sx, y*sy
        def text(x, y, value, size=11, color=WHITE, anchor='nw'):
            return c.create_text(*xy(x, y), text=value, fill=color,
                font=('Segoe UI', -max(8, round(size*font_scale))),
                anchor=anchor)
        def wire(points, power, color=GOLD, dashed=False):
            if power < 0:
                points = list(reversed(points))
            c.create_line(*(v for point in points for v in xy(*point)),
                fill=color if abs(power) > .01 else '#526479',
                width=2, arrow='last', arrowshape=(7, 9, 4),
                dash=(4, 4) if dashed else None)
        def card(col, y, title, value, lines, accent=TEAL, subtitle=''):
            x = 30 + col*235
            c.create_rectangle(*xy(x, y), *xy(x+195, y+114),
                fill='#192b3e', outline='#344b62')
            c.create_rectangle(*xy(x, y), *xy(x+195, y+3),
                fill=accent, outline='')
            text(x+13, y+14, title, 11, accent)
            text(x+13, y+36, value, 19)
            for n, line in enumerate(lines):
                text(x+13, y+66+n*17, line, 10, MUTED)
            return x
        p = model.parameters
        get = lambda name: r.get(name, 0.0)
        vdc = get('dc_voltage')
        export = get('electrical_export')
        brake = get('dc_brake_power')
        cap = r.get('excitation_mode') == 'capacitor'
        text(30, 16, 'LOWERING • ENERGY FLOW', 17)
        text(930, 20, ('PLAYING' if playing else 'PAUSED')+
             f'  /  {model.state.time:.1f} s', 11, MUTED, 'ne')
        text(30, 45, 'Capacitor only' if cap else 'Exciter only', 11, TEAL)
        text(930, 45, 'REAL POWER  →     REACTIVE  ⇄     HEAT  ↓', 10, GOLD, 'ne')

        # Auxiliary supply is adjacent to excitation. No feed crosses a machine.
        by = 78
        battery = get('battery_power')
        boost = get('boost_power')
        charger = abs(get('charger_power'))
        wire([(225,135),(265,135)], boost/max(p.boost_efficiency, .01))
        wire([(460,135),(500,135)], boost)
        wire([(833,192),(833,204),(8,204),(8,135),(30,135)], charger, TEAL)
        # Right perimeter routes charger feed clear of both main rows.
        wire([(598,546),(598,558),(950,558),(950,135),(930,135)], charger, TEAL)
        wire([(598,192),(598,216),(833,216),(833,265)],
             get('capacitor_reactive_supply') if cap else get('inverter_real_power'),
             PURPLE if cap else GOLD, cap)
        card(0,by,'24 V BATTERY',f"{get('battery_soc'):.1f}% SOC",
             [f"{get('battery_remaining_wh'):.1f} Wh remaining",
              f"{get('battery_voltage'):.1f} V   {get('battery_current'):+.2f} A   {battery:+.0f} W"])
        card(1,by,'BOOST / PRECHARGE',f'{boost:.0f} W',
             ['Battery → excitation',f"Heat {get('boost_loss'):.1f} W"])
        card(2,by,'CAPACITOR BANK' if cap else 'EXCITER',
             f"{get('capacitor_energy'):.2f} J" if cap else f"{get('inverter_real_power'):+.0f} W",
             [f"Q {get('capacitor_reactive_supply') if cap else get('inverter_reactive_supply'):+.0f} var",
              'Exciter disconnected' if cap else 'Capacitor bank disconnected'], PURPLE if cap else TEAL)
        card(3,by,'BATTERY CHARGER',f'{charger:.0f} W',
             ['DC link → 24 V battery','Charge input • teal route'],TEAL)

        text(30,239,'01  MECHANICAL → AC',10,MUTED)
        text(930,239,'↓ TO RECTIFIER',10,MUTED,'ne')
        y1,y2=265,432
        for i,power in enumerate((get('gravity_power'),-get('motor_shaft_power'),export)):
            wire([(225+235*i,322),(265+235*i,322)],power)
        wire([(833,379),(833,432)],get('rectifier_power'))
        for i,power in enumerate((brake,brake,get('dc_input_power'))):
            wire([(265+235*i,489),(225+235*i,489)],power)
        card(0,y1,'LOAD',f"{get('velocity'):+.2f} m/s",
             [f"Gravity {p.mass*p.gravity:.0f} N",
              f"{get('gravity_power'):+.0f} W released"],GOLD)
        card(1,y1,'GEAR / BEARINGS',f"{get('omega')*60/(2*math.pi):.0f} rpm",
             [f"Gear heat {get('gear_power'):.1f} W",
              f"Bearings {get('drivetrain_power'):.1f} W"])
        card(2,y1,'INDUCTION MACHINE',f'{export:+.0f} W AC',
             [f"{get('motor_torque'):+.1f} Nm   {get('machine_line_current'):.2f} A RMS",
              f"Q absorbed {get('machine_reactive_demand'):+.0f} var"])
        card(3,y1,'AC BUS',f"{get('line_voltage'):.1f} V",
             [f"Line–line RMS   {get('bus_frequency'):.2f} Hz",
              f"To bridge {get('rectifier_power'):+.0f} W"])
        text(30,407,'02  HEAT ← DC POWER',10,MUTED)
        text(930,407,'FLOW RIGHT TO LEFT',10,MUTED,'ne')
        card(0,y2,'BRAKE RESISTOR',f'{brake:.0f} W heat',
             [f'{p.dc_brake_resistance:g} ohm','Energy leaves to ambient'],HEAT)
        card(1,y2,'CHOPPER',f"{100*get('chopper_duty'):.0f}% duty",
             [f'Setpoint {p.chopper_threshold:g} V',f'{brake:.0f} W to resistor'],GOLD)
        card(2,y2,'DC LINK',f'{vdc:.1f} V DC',
             [f"{get('dc_energy'):.2f} J stored",f"Charger input {charger:.0f} W"])
        card(3,y2,'DIODE RECTIFIER',f"{get('dc_input_power'):.0f} W DC",
             [f"{get('rectifier_current'):.2f} A DC",f"Bridge heat {get('rectifier_loss'):.1f} W"])
        # Heat stays in a separate, readable footer, with no long text strip.
        text(30,585,'HEAT TO AMBIENT',11,HEAT)
        losses=[
            ('Machine copper', get('stator_loss')+get('rotor_loss')),
            ('Machine core',get('core_loss')),
            ('Exciter',get('inverter_loss')),
            ('Bridge',get('rectifier_loss'))]
        for col,(name,value) in enumerate(losses):
            x=30+235*col
            text(x,614,name,11,MUTED)
            text(x,635,f'{value:.1f} W',16,HEAT)
        text(30,671,'Positive battery current = discharge. Connection arrows follow signed power.',9,MUTED)
