"""Responsive animated overview. Gold = net real power, violet = reactive exchange."""
import math
from .visual_state import describe, energy_budget

GOLD = '#ffc36a'
PURPLE = '#b7a2ff'
TEAL = '#60e0c1'
MUTED = '#90a5bb'
WHITE = '#e5edf6'
BG = '#101b2c'


class EnergyView:
    def __init__(self, canvas, toggle_exciter):
        self.canvas = canvas
        self.toggle_exciter = toggle_exciter
        canvas.tag_bind('exciter', '<Button-1>', lambda event: toggle_exciter())
        canvas.tag_bind('exciter', '<Enter>', lambda event: canvas.configure(cursor='hand2'))
        canvas.tag_bind('exciter', '<Leave>', lambda event: canvas.configure(cursor=''))

    def draw(self, model, r, history, playing):
        c = self.canvas
        c.delete('all')
        # Expand both axes to the viewport. Keep readable minimum geometry;
        # small windows scroll instead of shrinking letters into illegibility.
        width, height = max(c.winfo_width(),1000), max(c.winfo_height(),1470)
        sx, sy = width/880, height/1470
        scale = min(sx, sy)
        c.configure(scrollregion=(0,0,width,height))
        v = describe(model,r,history)
        time = model.state.time  # particles freeze with the simulation
        native = False
        dc_on = r.get('rectifier_enabled',False)
        controlled = dc_on and r.get('chopper_active',False)
        limited = r.get('dc_exciter',False)
        external = r.get('external_exciter',False)
        def xy(x,y):
            if y>=543 and not native:
                y += 300
            return x*sx, y*sy
        def text(x,y,words,size=14,color=WHITE,anchor='nw',wrap=0,tags=()):
            return c.create_text(*xy(x,y),text=words,fill=color,
                font=('Segoe UI',-max(15,round(size*max(1,scale)))),anchor=anchor,
                width=wrap*sx if wrap else 0,tags=tags)
        def rect(x,y,w,h,fill,outline='',tags=()):
            return c.create_rectangle(*xy(x,y),*xy(x+w,y+h),fill=fill,outline=outline,
                                      width=max(1,scale),tags=tags)
        def oval(x,y,w,h,fill='',outline='',line=1,tags=()):
            return c.create_oval(*xy(x,y),*xy(x+w,y+h),fill=fill,outline=outline,
                                 width=max(1,line*scale),tags=tags)
        def line(points,color,width=2,arrow=None,dash=None):
            options=dict(fill=color,width=max(1,width*scale))
            if arrow:
                options.update(arrow=arrow,arrowshape=(9*scale,11*scale,5*scale))
            if dash:
                options['dash']=dash
            return c.create_line(*(coord for x,y in points for coord in xy(x,y)),**options)
        def particles(points, phase, color):
            segments=[math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(points,points[1:])]
            total=sum(segments)
            if total == 0:
                return
            for offset in (0,0.33,0.66):
                distance=((phase+offset)%1)*total
                for (a,b),length in zip(zip(points,points[1:]),segments):
                    if distance<=length:
                        f=distance/length if length else 0
                        oval(a[0]+f*(b[0]-a[0])-3,a[1]+f*(b[1]-a[1])-3,6,6,color)
                        break
                    distance-=length
        def flow(points,power,color=GOLD,reactive=False):
            live=abs(power)>0.1
            direction=points if power>=0 else list(reversed(points))
            thickness=2+min(4,math.log1p(abs(power))/2)
            line(direction,color if live else '#2f4154',thickness if live else 2,
                 arrow='both' if reactive and live else 'last' if live else None,
                 dash=(4,4) if reactive else None)
            if live:
                phase=time*0.5
                # Reactive exchange deliberately travels both ways: it is not
                # a source of continuous real energy. Animation is schematic.
                if reactive:
                    phase=0.45+0.4*math.sin(time*3)
                particles(direction,phase,color)
        def box(x,y,w,h,title,subtitle='',color=TEAL,tags=()):
            rect(x,y,w,h,'#192b3e','#30465d',tags)
            rect(x,y,4,h,color,tags=tags)
            text(x+14,y+12,title,17,tags=tags)
            if subtitle:
                text(x+14,y+40,subtitle,12,MUTED,wrap=w-24,tags=tags)
        def level(x,y,w,ratio,color):
            rect(x,y,w,9,'#2d4155')
            rect(x,y,w*min(1,max(0,ratio)),9,color)
        text(24,16,'SEE THE ENERGY MOVE',14,TEAL)
        text(856,16,f"{'PLAYING' if playing else 'PAUSED'}  ·  {time:.1f} s",12,MUTED,'ne')
        text(24,43,v['field_title'],25,WHITE,wrap=820)
        text(24,80,v['reason'],14,MUTED,wrap=824)

        # Real-power network: falling load <-> machine <-> AC bus <-> exciter/load.
        flow([(180,270),(285,270)],v['shaft_power'])
        flow([(485,270),(584,270)],v['terminal_export'])
        flow([(659,218 if limited or external else 188),(659,230)],v['source_power'])
        flow([(734,270),(772,270)],r.get('rectifier_power',0) if dc_on else v['load_power'])
        flow([(386,335),(386,419)],v['copper_power']+r.get('core_loss',0))
        # Capacitors exchange reactive current and can charge/discharge real energy.
        flow([(629,428),(629,312)],r['capacitor_reactive_supply'],PURPLE,True)
        flow([(686,312),(686,428)],v['cap_absorption'])
        flow([(558,155),(385,155),(385,220)],r['inverter_reactive_supply'],PURPLE,True)
        text(225,237,'shaft work',11,GOLD,'center')
        text(532,241,'electrical',11,GOLD,'center')
        text(456,177 if external else 136,'field exchange',12,PURPLE,'center')
        text(723,365,'stored /\nreleased',12,GOLD,'center')
        text(590,365,'field\nexchange',12,PURPLE,'center')
        text(24,165,f"{r['velocity']*60:.1f} m/min",26,GOLD)
        text(24,199,f"{r['clearance']:.1f} m above ground",13,MUTED)

        box(24,220,156,140,'Falling load',color=GOLD)
        # Hanging weight: travel follows actual displacement, without wrapping.
        fraction=min(1,max(0,model.state.position/model.parameters.crane_height))
        weight_y=277+30*fraction
        line([(61,267),(61,weight_y)],MUTED)
        rect(45,weight_y,32,24,'#c78f46')
        line([(90,270),(90,334)],'#48627b')
        oval(86,270+60*fraction,8,8,GOLD)
        text(104,291,'gravity',12,GOLD)
        text(102,339,'on ground' if model.state.grounded else 'moving' if abs(r['velocity'])>.005 else 'held',11,MUTED,'center')

        box(285,220,200,115,'Induction machine',color=TEAL)
        intensity=min(1,max(0,v['field_ratio']))
        glow=f'#{int(45+50*intensity):02x}{int(70+154*intensity):02x}{int(90+103*intensity):02x}'
        for radius in (21,28,35):
            oval(335-radius,294-radius,2*radius,2*radius,outline=glow,line=2)
        phase=model.state.angle%(2*math.pi)
        line([(335,294),(335+17*math.cos(phase),294+17*math.sin(phase))],WHITE,3)
        text(380,270,'magnetic\nfield',12,TEAL)
        level(374,311,90,v['field_ratio'],TEAL)

        box(584,230,150,82,'AC bus','voltage exists' if r['line_voltage']>.1 else 'voltage absent',color=TEAL if r['line_voltage']>.1 else MUTED)
        if external:
            flow([(224,137),(275,137),(275,116),(558,116)],r['external_supply_power'])
            box(24,115,200,44,f"400 V AC · {r['external_supply_power']:.1f} W",color=TEAL)
            box(558,113,190,105,'Small exciter ON' if model.inverter_enabled else 'Small exciter OFF',
                f"{r['inverter_reactive_supply']:+.0f} var · {r['inverter_real_power']:+.1f} W AC",tags=('exciter',))
            text(572,192,f"{r['inverter_current']:.2f} / {model.parameters.inverter_current_limit:g} A",13,MUTED,tags=('exciter',))
        elif limited:
            status=r['inverter_status'].replace('CURRENT + VOLTAGE LIMIT','I + V limited').replace('AC OVERVOLTAGE BLOCK','AC too high: blocked')
            box(558,113,190,105,'DC exciter ON' if model.inverter_enabled else 'DC exciter OFF',
                status,color=GOLD if 'LIMIT' in r['inverter_status'] or 'LOW' in r['inverter_status'] else TEAL,tags=('exciter',))
            text(572,193,f"{r['inverter_current']:.2f} / {model.parameters.inverter_current_limit:g} A",13,MUTED,tags=('exciter',))
        else:
            box(558,123,190,65,'Exciter ON' if model.inverter_enabled else 'Exciter OFF','click to switch',color=TEAL if model.inverter_enabled else MUTED,tags=('exciter',))
        if not v['dynamic']:
            text(558,107,'Includes ideal real-power boundary',10,MUTED)
        box(772,231,84,106,'Diodes' if dc_on else 'Load',
            'AC → DC' if dc_on else 'heat',color=TEAL if dc_on else '#ff977a')
        heat_level=min(1,max(0,v['load_power'])/100)
        if dc_on:
            text(814,309,'passing' if r['rectifier_current']>.001 else 'blocked',12,MUTED,'center')
        else:
            for x in (790,811,832):
                line([(x,313),(x-3,300),(x+3,289)],'#ff977a' if heat_level>.001 else '#465469',2)
        box(302,419,168,73,'Machine heat' if external else 'Winding losses',
            f"Cu {v['copper_power']:.0f} W · Fe {r.get('core_loss',0):.0f} W" if external else 'copper heating',color='#ff977a')
        text(384,382,'heat',11,'#ff977a','center')

        cap_title='Capacitors' if model.capacitors_enabled else 'Caps disconnected'
        box(568,428,188,85,cap_title,color=PURPLE if model.capacitors_enabled else MUTED)
        level(582,470,156,v['voltage_ratio'] if model.capacitors_enabled else 0,PURPLE)
        text(582,485,f"{r.get('capacitor_energy',0):.2f} J stored",11,MUTED)
        text(24,389,'What is happening?',14,WHITE)
        text(24,416,v['motion'],17,GOLD,wrap=250)
        text(24,467,v['torque_text'],13,MUTED,wrap=250)

        native = True
        if dc_on:
            flow([(814,337),(814,600),(756,600)],r['dc_input_power'])
            flow([(568,600),(485,600)],r['dc_brake_power'])
            if controlled:
                flow([(285,600),(244,600)],r['dc_brake_power'])
            if limited:
                flow([(756,650),(867,650),(867,102),(730,102),(730,113)],r['inverter_dc_power'])
        box(568,555,188,112,'DC bus',color=TEAL if dc_on else MUTED)
        text(582,593,f"{r.get('dc_voltage',0):.1f} V DC" if dc_on else 'disconnected',19,WHITE)
        level(582,626,156,r.get('dc_voltage',0)/((math.sqrt(2) if external else 1.35)*model.parameters.motor_rated_voltage) if dc_on else 0,TEAL)
        text(582,644,f"{r.get('dc_energy',0):.2f} J stored",13,MUTED)
        resistor_x=24 if controlled else 285
        box(resistor_x,555,220 if controlled else 200,112,'Brake resistor',color='#ff977a' if dc_on else MUTED)
        text(resistor_x+14,594,f"{r.get('dc_brake_power',0):.0f} W heat",19,'#ff977a')
        text(resistor_x+14,626,f"{model.parameters.dc_brake_resistance:g} ohm",13,MUTED)
        if controlled:
            box(285,555,200,112,'Brake chopper',color=GOLD)
            text(299,590,f"{100*r['chopper_duty']:.0f}% duty",19,GOLD)
            level(299,620,172,r['chopper_duty'],GOLD)
            at_limit=r['chopper_command']>=model.parameters.chopper_max_duty and r['dc_voltage']>model.parameters.chopper_threshold
            text(299,641,('AT DUTY LIMIT' if abs(r['chopper_duty']-r['chopper_command'])<.01 else 'RAMPING TO LIMIT') if at_limit
                 else 'disabled' if not r['chopper_enabled'] else 'regulating' if r['chopper_duty']>.001 else 'waiting',13,MUTED)
        elif not dc_on:
            text(24,584,'Enable the DC path in Explore to replace the AC test load.',14,MUTED,wrap=235)
        if external:
            box(24,700,240,100,'External supply / exciter')
            text(38,738,f"Supply {r['external_supply_power']:.1f} W · AC {r['inverter_real_power']:+.1f} W",15,WHITE)
            text(38,773,f"Converter heat {r['inverter_loss']:.1f} W",13,MUTED)
            box(285,700,240,100,'Passive power path',color=GOLD)
            text(299,738,f"Bridge AC {r['rectifier_power']:.0f} W",15,WHITE)
            text(299,773,f"Into DC {r['dc_input_power']:.0f} W",13,MUTED)
            box(550,700,306,100,'Mechanical losses',color='#c5a178')
            text(564,738,f"Gear {r['gear_power']:.1f} W · bearings {r['drivetrain_power']:.1f} W",15,WHITE)
            text(564,773,f"Brake {r['brake_power']:.1f} W · viscous {r['friction_power']:.1f} W",13,MUTED)
            text(24,812,'External supply feeds the small exciter. Generated watts use the passive bridge and DC brake.',13,MUTED)
        else:
            boost_on=r.get('boost_enabled',False)
            flow([(224,750),(285,750)],r.get('battery_power',0))
            flow([(485,750),(530,750),(530,650),(568,650)],r.get('boost_power',0))
            box(24,700,200,100,f'{model.parameters.battery_voltage:g} V battery',color=TEAL if boost_on else MUTED)
            text(38,738,f"{r.get('battery_power',0):.1f} W · {r.get('battery_current',0):.2f} A",17,WHITE)
            text(38,773,f"{r.get('battery_energy',0)/3600:.3f} Wh used",13,MUTED)
            box(285,700,200,100,'Boost support',color=TEAL if boost_on else MUTED)
            text(299,738,r.get('boost_status','OFF'),15,TEAL if boost_on else MUTED)
            text(299,773,f"{r.get('boost_power',0):.1f} W to DC",13,MUTED)
            text(568,714,f"Target {model.parameters.boost_target_voltage:g} V\nBattery limit {model.parameters.boost_input_power_limit:g} W\nBoost loss {r.get('boost_loss',0):.1f} W",14,MUTED,wrap=280)
            text(24,812,(f"DC-fed exciter: {r['inverter_loss']:.1f} W loss · voltage ceiling {r['inverter_voltage_limit']:.0f} V AC · 24 V support shown above" if limited
                 else f"Chopper starts above {model.parameters.chopper_threshold:g} V; finite duty response. Exciter still ideal/external." if controlled
                 else 'Phase 5: averaged rectifier and directly connected equivalent resistance.'),13,MUTED)
        native = False

        # Three simple visual comparisons, explicitly referenced, not safety ratings.
        rect(24,543,832,114,'#17283b','#30465d')
        text(40,556,'MAGNETIC FIELD',12,TEAL)
        level(40,585,226,v['field_ratio'],TEAL)
        text(40,605,'seed' if v['field_ratio']<.02 else 'building' if v['field_rate']>.03 else 'fading' if v['field_rate']<-.03 else 'present',15,WHITE)
        text(40,636,'brightness follows flux',10,MUTED)
        text(309,556,'AC VOLTAGE / RATED',12,PURPLE)
        level(309,585,226,v['voltage_ratio'],PURPLE)
        text(309,605,f"{r['line_voltage']:.0f} V · {100*v['voltage_ratio']:.0f}%",15,WHITE)
        text(309,636,f"100% = {model.parameters.motor_rated_voltage:g} V line RMS",10,MUTED)
        text(578,556,'ELECTRICAL BRAKING',12,GOLD)
        gravity_torque=model.parameters.mass*model.parameters.gravity*model.parameters.radius
        opposition=max(0,-r['motor_torque'])
        level(578,585,258,opposition/max(gravity_torque,1e-9),GOLD)
        text(578,605,'opposes gravity' if opposition>.1 else 'little / no opposition',15,WHITE)
        text(578,636,'full = gravity torque',13,MUTED)
        text(24,674,'Gold: net power.  Purple: reactive exchange.  Dots pause with the simulation.',13,MUTED)
        text(24,698,'Voltage bars show rated-voltage references; stored energy is shown in joules.',13,MUTED)

        budget = energy_budget(model,r)
        if budget is None:
            text(24,742,'Energy inventory is available in dynamic mode.',17,MUTED)
            return
        colors = ['#658cae', GOLD, PURPLE, '#ff977a', '#ec657b', '#c5a178', TEAL, '#68bbf3','#ff7649','#c880a9','#e0cc87','#83d4be','#d5b6eb','#d99e71','#7cbdcb','#bbc580']
        text(24,736,'WHERE THE ENERGY GOES',18,TEAL)
        text(856,739,f"Height energy released: {budget['released']/1000:.2f} kJ",14,WHITE,'ne')
        total = max(budget['total'],1e-12)
        text(24,768,f"Available: {total/1000:.2f} kJ = initial height + initial stored energy + net external input",14,MUTED)
        x = 24
        for index, (name, value) in enumerate(budget['outputs']):
            extent = 832*max(0,value)/total
            rect(x,799,extent,25,colors[index])
            x += extent
        # A common absolute scale preserves the large remaining-height share.
        # Individual tracks below make even small destinations understandable.
        for index, (name,value) in enumerate(budget['outputs']):
            column, row = index%2, index//2
            x, y = 24+column*425, 839+row*36
            rect(x,y+3,9,13,colors[index])
            text(x+16,y,name,13,WHITE)
            text(x+403,y,f'{value/1000:.3f} kJ',13,WHITE,'ne')
            level(x+16,y+23,387,value/total,colors[index])
        text(24,1108,f"Balance error: {budget['residual']:.3f} J",13,MUTED)
        text(24,1135,f"Initial stored: {model.initial_energy/1000:.3f} kJ  |  Battery: {r.get('battery_energy',0)/1000:.3f} kJ  |  Other external: {r['source_energy']/1000:+.3f} kJ",13,MUTED)
