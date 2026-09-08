"""Connection-led power diagram; all physics comes from model diagnostics."""
import math

GOLD, PURPLE, TEAL, HEAT = '#ffc36a', '#b7a2ff', '#60e0c1', '#ff977a'
WHITE, MUTED, BG = '#e5edf6', '#a6b6c8', '#101b2c'


class EnergyView:
    def __init__(self, canvas, toggle_exciter):
        self.canvas=canvas
        self.toggle_exciter=toggle_exciter
        canvas.bind('<Button-1>',self.click)
        self.clock=0.

    def click(self,event):
        x=event.x*960/max(1,self.canvas.winfo_width())
        y=event.y*690/max(1,self.canvas.winfo_height())
        if 710<=x<=830 and 145<=y<=245:
            self.model.charger_enabled=not self.model.charger_enabled
        elif 450<=x<=550 and 145<=y<=245 and self.model.excitation_mode=='exciter':
            self.toggle_exciter()

    def draw(self, model, r, history, playing):
        self.model=model
        c=self.canvas
        c.delete('all')
        width,height=max(1,c.winfo_width()),max(1,c.winfo_height())
        sx,sy=width/960,height/690
        c.configure(scrollregion=(0,0,width,height))
        if playing:self.clock=model.state.time
        t=self.clock
        def xy(x,y):return x*sx,y*sy
        def text(x,y,value,size=11,color=WHITE,anchor='n'):
            return c.create_text(*xy(x,y),text=value,fill=color,font=('Segoe UI',-max(12,round(size*min(sx,sy)))),anchor=anchor,justify='center')
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
            text(x,y+82,state,11,MUTED)
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
        line([(770,145),(770,66),(70,66),(70,145)],ports['charger_battery']['power'],TEAL)
        text(400,70,f"Charge: {ports['charger_battery']['voltage']:.1f} V | {ports['charger_battery']['current']:.2f} A | {ports['charger_battery']['power']:.1f} W \u2190",11,TEAL)
        line([(661,350),(661,262),(925,262),(925,195),(830,195)],ports['dc_charger']['power'],TEAL)
        transfer(860,96,ports['dc_charger'])
        c.create_line(*xy(860,150),*xy(860,190),fill='#46596f')
        # Auxiliary supply cards and their own short connection lanes.
        card(70,145,'BATTERY',f"{r['battery_soc']:.1f}% SOC",100)
        level(70,190,r['battery_soc']/100,f"{r['battery_remaining_wh']:.1f} Wh")
        card(220,145,'BOOST','averaged',90)
        card(360,145,'AUX HV LINK','C_aux',110)
        level(360,190,r['aux_voltage']/p.boost_target_voltage,f"{r['aux_voltage']:.0f} V | {r['aux_energy']:.1f} J")
        card(500,145,('CAP + START' if r['startup_support'] else 'CAP BANK') if cap else 'EXCITER',f"dE {comp['capacitor']['storage_rate']:+.2g} W" if cap else 'flux control',100)
        if cap:level(500,190,r['capacitor_energy']/max(1,.5*model.kernel.cac*400**2),f"{r['capacitor_energy']:.2f} J")
        else:
            c.create_rectangle(*xy(450,145),*xy(550,245),fill='',outline='',tags='exciter')
            text(500,193,f"{r['inverter_current']:.2f} A RMS",12,PURPLE)
        card(770,145,'CHARGER','ON - click' if model.charger_enabled else 'OFF - click',120)
        text(770,191,f"{p.charger_efficiency*100:.0f}% eff.",12)
        for a,b,name in ((120,175,'battery_boost'),(265,305,'boost_aux'),(415,450,'aux_exciter')):
            line([(a,177),(b,177)],ports[name]['power'])
            transfer((a+b)/2,96,ports[name])
        for x,name in ((70,'battery'),(220,'boost'),(770,'charger')):
            line([(x,245),(x,260)],comp[name]['heat'],HEAT)
            text(x,263,f"{comp[name]['heat']:.1f} W heat",11,HEAT)
        text(750,626,f"Battery {r['battery_voltage']:.2f} V | {r['battery_current']:+.2f} A | {r['battery_power']:+.1f} W",11,MUTED)
        # Excitation connects to the bus in the clear lane between port labels.
        port=ports['aux_bus']
        real=port['power']
        line([(500,245),(500,310),(419,310),(419,350)],real)
        line([(512,245),(512,322),(431,322),(431,350)],port['reactive'],PURPLE,True)
        transfer(585,180,port)
        if not cap or r['startup_support']:
            text(590,327,f"{comp['exciter']['heat']:.1f} W exciter heat",11,HEAT)
            line([(548,245),(560,245),(560,322),(575,322)],comp['exciter']['heat'],HEAT)
        # Entire primary path stays left to right.
        centers=[56+121*i for i in range(8)]
        titles=['LOAD','GEAR /\nBEARINGS','INDUCTION\nMACHINE','AC BUS','RECTIFIER','DC LINK','CHOPPER','BRAKE\nRESISTOR']
        states=[f"{r['position']:.2f} m",'shaft',f"{r['flux_magnitude']:.2g} Wb",f"{r['bus_frequency']:.1f} Hz",r['main_dc_connection'],f"{r['dc_energy']:.1f} J",f"{r['chopper_duty']*100:.0f}% duty",f"{p.dc_brake_resistance:.0f} ohm"]
        for x,title,state in zip(centers,titles,states):card(x,350,title,state)
        names=['load_gear','gear_machine','machine_bus','bus_rectifier','rectifier_dc','dc_chopper','chopper_resistor']
        for i,name in enumerate(names):
            a,b=centers[i]+40,centers[i+1]-40
            line([(a,389),(b,389)],ports[name]['power'])
            # The AC BUS to rectifier readout is the block immediately right
            # of AC BUS.  Put only that block below the component row.
            transfer((a+b)/2,470 if name=='bus_rectifier' else 282,ports[name])
            if name=='bus_rectifier':
                # Keep the moved readout connected to its AC-to-rectifier path.
                c.create_line(*xy((a+b)/2,412),*xy((a+b)/2,465),fill='#46596f')
            else:
                c.create_line(*xy((a+b)/2,347),*xy((a+b)/2,386),fill='#46596f')
            if ports[name]['kind']=='ac':line([(a,410),(b,410)],ports[name]['reactive'],PURPLE,True)
        # Physical state glyphs are embedded in the compact cards.
        y=383+33*math.log1p(max(0,r['position']))/math.log1p(max(p.crane_height,1e-9))
        c.create_line(*xy(56,383),*xy(56,y),fill=MUTED,width=2)
        c.create_rectangle(*xy(47,y),*xy(65,y+10),fill=GOLD,outline='')
        x=centers[2];flux=min(1,r['flux_magnitude']/p.exciter_flux_target)
        color='#%02x%02x%02x'%(int(45+70*flux),int(65+150*flux),int(95+140*flux))
        c.create_oval(*xy(x-18,395),*xy(x+18,425),outline=color,width=2+3*flux)
        angle=model.state.angle
        self.angle=angle
        c.create_line(*xy(x,410),*xy(x+15*math.cos(angle),410+15*math.sin(angle)),fill=GOLD,width=3)
        level(centers[5],393,r['dc_voltage']/max(p.chopper_threshold,1),f"{r['dc_voltage']:.0f} V")
        level(centers[6],393,r['chopper_duty'],'PWM')
        pulse=GOLD if (t*8)%1<r['chopper_duty'] else '#526479'
        c.create_oval(*xy(centers[6]+26,398),*xy(centers[6]+32,404),fill=pulse,outline='')
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
        # Field lines use logarithmic brightness so a real residual seed is
        # visible. The measured flux and percentage retain their true scale.
        field=r['flux_magnitude']
        ratio=field/max(p.exciter_flux_target,1e-12)
        strength=min(1.,math.log1p(1000*ratio)/math.log(1001))
        field_color='#%02x%02x%02x'%(int(40+55*strength),int(60+160*strength),int(80+150*strength))
        c.create_rectangle(*xy(750,520),*xy(938,615),fill='#142338',outline='#41556d')
        text(844,523,'MACHINE MAGNETIC FIELD',12,TEAL)
        phase=r.get('flux_angle',0.)
        for radius in (38,29,20):
            points=[]
            for j in range(41):
                theta=2*math.pi*j/40
                a,b=radius*math.cos(theta),12*math.sin(theta)
                points.extend(xy(844+a*math.cos(phase)-b*math.sin(phase)*.3,
                                 558+a*math.sin(phase)*.3+b*math.cos(phase)))
            c.create_line(*points,fill=field_color,width=1+2*strength)
        label='ZERO FIELD' if field<1e-12 else f'{field:.3g} Wb | {100*ratio:.2g}%'
        text(844,580,label,12,TEAL)
        text(844,598,'Brightness: log scale',11,MUTED)
        line([(20,245),(9,245),(9,625),(50,625)],comp['battery']['storage_rate'],TEAL)
        text(160,626,f"Battery storage {comp['battery']['storage_rate']:+.1f} W",11,TEAL)
        text(480,647,f"Conservation residual {r['energy_residual']:+.6f} J   |   AC KCL {abs(d['kcl']):.2e} A",11,MUTED)
        text(480,669,'Signed battery current: + discharge / - charge. Ieq: averaged bridge fundamental equivalent.',11,MUTED)
