"""Connection-led power diagram; all physics comes from model diagnostics."""
import math

GOLD, PURPLE, TEAL, HEAT = '#ffc36a', '#b7a2ff', '#60e0c1', '#ff977a'
WHITE, MUTED, BG = '#e5edf6', '#a6b6c8', '#101b2c'


class EnergyView:
    def __init__(self, canvas, toggle_exciter):
        self.canvas=canvas
        self.toggle_exciter=toggle_exciter
        canvas.tag_bind('exciter','<Button-1>',lambda event:self.toggle_exciter())
        self.clock=0.

    def draw(self, model, r, history, playing):
        c=self.canvas
        c.delete('all')
        width,height=max(1,c.winfo_width()),max(1,c.winfo_height())
        sx,sy=width/960,height/690
        c.configure(scrollregion=(0,0,width,height))
        if playing:self.clock=model.state.time
        t=self.clock
        def xy(x,y):return x*sx,y*sy
        def text(x,y,value,size=11,color=WHITE,anchor='n'):
            return c.create_text(*xy(x,y),text=value,fill=color,font=('Segoe UI',-max(11,round(size*min(sx,sy)))),anchor=anchor,justify='center')
        def line(points,power,color=GOLD,reactive=False):
            pts=list(points)
            if power<0 and not reactive:pts.reverse()
            coords=[z for point in pts for z in xy(*point)]
            c.create_line(*coords,fill=color if abs(power)>.01 else '#45566a',width=2 if reactive else 3,arrow='both' if reactive else 'last',arrowshape=(6,8,3),dash=(3,4) if reactive else None)
            if abs(power)<.01:return
            lengths=[math.dist(a,b) for a,b in zip(pts,pts[1:])]
            length=sum(lengths)
            for j in range(3):
                f=(.5+.42*math.sin(2*math.pi*t*1.4+j*1.5)) if reactive else (t*(.22+.08*math.log1p(abs(power)))+j/3)%1
                distance=f*length
                for n,segment in enumerate(lengths):
                    if distance<=segment:
                        a,b=pts[n:n+2];q=distance/max(segment,1e-9)
                        x,y=xy(a[0]+q*(b[0]-a[0]),a[1]+q*(b[1]-a[1]))
                        c.create_oval(x-2.5,y-2.5,x+2.5,y+2.5,fill=color,outline='')
                        break
                    distance-=segment
        def transfer(x,y,port):
            kind=port['kind'];power=port['power']
            arrow='→' if power>=0 else '←'
            if kind=='ac':
                values=f"{port['voltage']:.0f} V LL RMS\n{port['current']:.2f} A {'Ieq' if port['equivalent'] else 'RMS'}"
            elif kind=='dc':values=f"{port['voltage']:.0f} V DC\n{port['current']:.2f} A DC"
            elif kind=='shaft':values=f"{port['torque']:.2f} Nm\n{port['rpm']:.0f} rpm"
            else:values=f"{port['force']:.0f} N\n{port['velocity']*60:.1f} m/min"
            text(x,y,values,11,MUTED)
            text(x,y+32,f"{abs(power):.1f} W {arrow}",12,GOLD)
            if kind=='ac':text(x,y+50,f"Q {port['reactive']:+.0f} var ⇄",11,PURPLE)
        def card(x,y,title,state='',w=80):
            c.create_rectangle(*xy(x-w/2,y),*xy(x+w/2,y+100),fill='#1b2d42',outline='#41556d')
            text(x,y+8,title,12,TEAL)
            text(x,y+75,state,11,MUTED)
        def level(x,y,fraction,label):
            fraction=max(0,min(1,fraction))
            c.create_rectangle(*xy(x-23,y),*xy(x+23,y+14),fill='#0c1725',outline='#526479')
            c.create_rectangle(*xy(x-22,y+1),*xy(x-22+44*fraction,y+13),fill=TEAL,outline='')
            text(x,y+18,label,11,MUTED)
        d=r.get('power_diagnostics')
        if not d:
            text(480,250,'Energy diagnostics require the battery / exciter model.',14)
            return
        comp,ports=d['components'],d['connections']
        p=model.parameters
        cap=model.excitation_mode=='capacitor'
        text(18,14,'ENERGY FLOW',18,WHITE,'nw')
        text(942,18,f"{'RUNNING' if playing else 'PAUSED'}  |  {model.state.time:.2f} s",12,MUTED,'ne')
        text(480,46,'REAL →  gold     REACTIVE ⇄  purple     HEAT ↓  coral     STORAGE ↕  mint',11)
        # Two dedicated perimeter lanes: charger output above, DC feed right.
        line([(770,145),(770,78),(70,78),(70,145)],ports['charger_battery']['power'],TEAL)
        text(400,82,f"Charge: {ports['charger_battery']['voltage']:.1f} V | {ports['charger_battery']['current']:.2f} A | {ports['charger_battery']['power']:.1f} W \u2190",11,TEAL)
        line([(661,350),(661,262),(925,262),(925,195),(830,195)],ports['dc_charger']['power'],TEAL)
        transfer(860,96,ports['dc_charger'])
        c.create_line(*xy(860,150),*xy(860,190),fill='#46596f')
        # Auxiliary supply cards and their own short connection lanes.
        card(70,145,'BATTERY',f"{r['battery_soc']:.1f}% SOC",100)
        level(70,190,r['battery_soc']/100,f"{r['battery_remaining_wh']:.1f} Wh")
        card(270,145,'BOOST','regulated DC',100)
        level(270,190,ports['boost_exciter']['voltage']/p.boost_target_voltage,f"{p.boost_target_voltage:.0f} V")
        card(430,145,'CAP BANK' if cap else 'EXCITER','connected' if cap else 'flux control',100)
        if cap:level(430,190,r['capacitor_energy']/max(1,.5*model.kernel.cac*400**2),f"{r['capacitor_energy']:.2f} J")
        else:
            c.create_rectangle(*xy(380,145),*xy(480,245),fill='',outline='',tags='exciter')
            text(430,193,f"{r['inverter_current']:.2f} A RMS",12,PURPLE)
        card(770,145,'CHARGER','isolated DC',120)
        text(770,191,f"{p.charger_efficiency*100:.0f}% eff.",12)
        for a,b,name in ((120,220,'battery_boost'),(320,380,'boost_exciter')):
            line([(a,177),(b,177)],ports[name]['power'])
            transfer((a+b)/2,96,ports[name])
        for x,name in ((70,'battery'),(270,'boost'),(770,'charger')):
            line([(x,245),(x,260)],comp[name]['heat'],HEAT)
            text(x,263,f"{comp[name]['heat']:.1f} W heat",11,HEAT)
        text(750,626,f"Battery {r['battery_voltage']:.2f} V | {r['battery_current']:+.2f} A | {r['battery_power']:+.1f} W",11,MUTED)
        # Excitation connects to the bus in the clear lane between port labels.
        name='bus_capacitor' if cap else 'exciter_bus'
        port=ports[name]
        real= -port['power'] if cap else port['power']
        line([(420,245),(420,350)],real)
        line([(432,245),(432,350)],port['reactive'],PURPLE,True)
        transfer(553,180,port)
        line([(480,195),(490,195)],real)
        text(553,248,f"{comp['exciter']['heat']:.1f} W exciter heat",11,HEAT)
        line([(468,245),(468,253),(490,253)],comp['exciter']['heat'],HEAT)
        # Entire primary path stays left to right.
        centers=[56+121*i for i in range(8)]
        titles=['LOAD','GEAR /\nBEARINGS','INDUCTION\nMACHINE','AC BUS','RECTIFIER','DC LINK','CHOPPER','BRAKE\nRESISTOR']
        states=[f"{r['position']:.2f} m",'shaft',f"{r['flux_magnitude']:.2f} Wb",f"{r['bus_frequency']:.1f} Hz",'averaged',f"{r['dc_energy']:.1f} J",f"{r['chopper_duty']*100:.0f}% duty",f"{p.dc_brake_resistance:.0f} ohm"]
        for x,title,state in zip(centers,titles,states):card(x,350,title,state)
        names=['load_gear','gear_machine','machine_bus','bus_rectifier','rectifier_dc','dc_chopper','chopper_resistor']
        for i,name in enumerate(names):
            a,b=centers[i]+40,centers[i+1]-40
            line([(a,389),(b,389)],ports[name]['power'])
            transfer((a+b)/2,282,ports[name])
            c.create_line(*xy((a+b)/2,347),*xy((a+b)/2,386),fill='#46596f')
            if ports[name]['kind']=='ac':line([(a,410),(b,410)],ports[name]['reactive'],PURPLE,True)
        # Physical state glyphs are embedded in the compact cards.
        y=383+33*math.log1p(max(0,r['position']))/math.log1p(max(p.crane_height,1e-9))
        c.create_line(*xy(56,383),*xy(56,y),fill=MUTED,width=2)
        c.create_rectangle(*xy(47,y),*xy(65,y+10),fill=GOLD,outline='')
        x=centers[2];flux=min(1,r['flux_magnitude']/p.exciter_flux_target)
        color='#%02x%02x%02x'%(int(45+70*flux),int(65+150*flux),int(95+140*flux))
        c.create_oval(*xy(x-18,388),*xy(x+18,422),outline=color,width=2+3*flux)
        angle=model.state.angle if playing else getattr(self,'angle',model.state.angle)
        self.angle=angle
        c.create_line(*xy(x,405),*xy(x+15*math.cos(angle),405+15*math.sin(angle)),fill=GOLD,width=3)
        level(centers[5],393,r['dc_voltage']/max(p.chopper_threshold,1),f"{r['dc_voltage']:.0f} V")
        level(centers[6],393,r['chopper_duty'],'PWM')
        # Each heat/storage branch is attached to its originating component.
        keys=['load','gear','machine','ac_bus','rectifier','dc_link','chopper','resistor']
        for x,key in zip(centers,keys):
            item=comp[key]
            if key in ('gear','machine','rectifier','resistor'):
                line([(x-12,450),(x-12,480)],item['heat'],HEAT)
                label=(f"Cu {item['copper']:.1f} W\nFe {item['core']:.1f} W" if key=='machine' else f"{item['heat']:.1f} W heat")
                text(x,485,label,11,HEAT)
                if key=='rectifier':text(x,519,'bridge / source',11,MUTED)
            if key in ('load','gear','machine','dc_link'):
                flow=item['storage_rate']
                line([(x+29,450),(x+53,450),(x+53,550),(x,550)],flow,TEAL)
                label={'load':'Height energy','gear':'Kinetic energy','machine':'Magnetic field','dc_link':'DC capacitor'}[key]
                text(x,561,label,11,TEAL)
                text(x,582,f"{flow:+.1f} W\n{item['energy']:.2f} J",11,TEAL)
        text(553,269,f"{comp['capacitor']['storage_rate']:+.1f} W stored" if cap else '',11,TEAL)
        line([(20,245),(9,245),(9,596),(25,596)],comp['battery']['storage_rate'],TEAL)
        text(160,626,f"Battery storage {comp['battery']['storage_rate']:+.1f} W",11,TEAL)
        text(480,647,f"Conservation residual {r['energy_residual']:+.6f} J   |   AC KCL {abs(d['kcl']):.2e} A",11,MUTED)
        text(480,669,'Signed battery current: + discharge / - charge. Ieq: averaged bridge fundamental equivalent.',11,MUTED)
