"""Persistent connection-led power diagram.

The model owns physics and diagnostics. This view creates canvas objects only
when its layout/topology changes, then mutates those objects during animation.
"""
import math

GOLD, PURPLE, TEAL, HEAT = '#ffc36a', '#b7a2ff', '#60e0c1', '#ff977a'
WHITE, MUTED, BG = '#e5edf6', '#a6b6c8', '#101b2c'


class EnergyView:
    DESIGN_WIDTH = 960
    DESIGN_HEIGHT = 690

    def __init__(self, canvas, toggle_exciter):
        self.canvas = canvas
        self.toggle_exciter = toggle_exciter
        self.model = None
        self.items = {}
        self.flows = {}
        self.levels = {}
        self.text_cache = {}
        self.layout_signature = None
        self.topology_signature = None
        self.telemetry = None
        self.visual_time = 0.0
        self.created_once = 0
        self.updates_last_frame = 0
        canvas.bind('<Button-1>', self.click)

    def click(self, event):
        if self.model is None:
            return
        x = event.x*self.DESIGN_WIDTH/max(1, self.canvas.winfo_width())
        y = event.y*self.DESIGN_HEIGHT/max(1, self.canvas.winfo_height())
        if 710 <= x <= 830 and 145 <= y <= 245:
            self.model.charger_enabled = not self.model.charger_enabled
        elif (450 <= x <= 550 and 145 <= y <= 245
              and self.model.excitation_mode == 'exciter'):
            self.toggle_exciter()

    def draw(self, model, readings, history, playing, *, visual_time=None,
             update_text=True):
        """Compatibility facade used by the UI and rendering tests."""
        self.model = model
        self.update_layout_if_needed(model, readings)
        self.update_telemetry(model, readings, playing, update_text=update_text)
        sample_time = readings.get('_time', model.state.time)
        self.update_animation(readings, sample_time if visual_time is None else visual_time,
                              playing)

    def update_layout_if_needed(self, model, readings, force=False):
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        layout = (width, height)
        topology = (bool(readings.get('power_diagnostics')),
                    model.excitation_mode == 'capacitor')
        resized = (self.layout_signature is None
                   or abs(width-self.layout_signature[0]) >= 8
                   or abs(height-self.layout_signature[1]) >= 8)
        if force or resized or topology != self.topology_signature:
            self.layout_signature = layout
            self.topology_signature = topology
            self.build_static_scene(model, readings)
            self.build_dynamic_items(model, readings)

    def refresh(self):
        """Request the supported full scene rebuild on the next draw."""
        self.layout_signature = None

    def _clear_scene(self):
        # Deliberately scoped: normal animation never deletes canvas objects,
        # and even a resize does not destroy objects owned by another view.
        self.canvas.delete('energy_scene')
        self.items.clear()
        self.flows.clear()
        self.levels.clear()
        self.text_cache.clear()

    def _xy(self, x, y):
        width, height = self.layout_signature
        return x*width/self.DESIGN_WIDTH, y*height/self.DESIGN_HEIGHT

    def _font(self, size):
        width, height = self.layout_signature
        scale = min(width/self.DESIGN_WIDTH, height/self.DESIGN_HEIGHT)
        return ('Segoe UI', -max(12, round(size*scale)))

    def _remember(self, key, item):
        self.items[key] = item
        return item

    def _text(self, key, x, y, value='', size=11, color=WHITE, anchor='n'):
        item = self.canvas.create_text(
            *self._xy(x, y), text=value, fill=color, font=self._font(size),
            anchor=anchor, justify='center', tags=('energy_scene',))
        self._remember(key, item)
        self.text_cache[key] = value
        return item

    def _fixed_line(self, key, points, color='#46596f', width=1, **options):
        coords = [v for point in points for v in self._xy(*point)]
        item = self.canvas.create_line(
            *coords, fill=color, width=width, tags=('energy_scene',), **options)
        return self._remember(key, item)

    def _card(self, key, x, y, title, width=80):
        self._remember(key+'_box', self.canvas.create_rectangle(
            *self._xy(x-width/2, y), *self._xy(x+width/2, y+100),
            fill='#1b2d42', outline='#41556d', tags=('energy_scene',)))
        self._text(key+'_title', x, y+8, title, 12, TEAL)
        self._text(key+'_state', x, y+82, '', 11, MUTED)

    def _level(self, key, x, y):
        self.canvas.create_rectangle(
            *self._xy(x-23, y), *self._xy(x+23, y+14), fill='#0c1725',
            outline='#526479', tags=('energy_scene',))
        fill = self.canvas.create_rectangle(
            *self._xy(x-22, y+1), *self._xy(x-22, y+13), fill=TEAL,
            outline='', tags=('energy_scene',))
        self.levels[key] = (fill, x, y)
        self._text(key+'_label', x, y+18, '', 11, MUTED)

    def _flow(self, key, points, color=GOLD, reactive=False):
        coords = [v for point in points for v in self._xy(*point)]
        line = self.canvas.create_line(
            *coords, fill='#45566a', width=2 if reactive else 3,
            arrow='both' if reactive else 'last', arrowshape=(6, 8, 3),
            dash=(3, 4) if reactive else None, tags=('energy_scene',))
        particles = [self.canvas.create_oval(
            0, 0, 0, 0, fill=color, outline='', state='hidden',
            tags=('energy_scene',)) for _ in range(3)]
        self.flows[key] = dict(line=line, points=tuple(points), color=color,
                               reactive=reactive, particles=particles,
                               style=None, visible=[False, False, False])

    def _transfer(self, key, x, y, kind):
        self._text(key+'_values', x, y, '', 11, MUTED)
        self._text(key+'_power', x, y+32, '', 12, GOLD)
        if kind == 'ac':
            self._text(key+'_reactive', x, y+50, '', 11, PURPLE)

    def build_static_scene(self, model, readings):
        self._clear_scene()
        c = self.canvas
        width, height = self.layout_signature
        c.configure(scrollregion=(0, 0, width, height))
        self._text('heading', 18, 14, 'ENERGY FLOW', 18, WHITE, 'nw')
        self._text('status', 942, 18, '', 12, MUTED, 'ne')
        self._text('legend', 480, 46,
                   'REAL →  gold     REACTIVE ⇄  purple     HEAT ↓  coral     STORAGE ↕  mint',
                   11)
        if not readings.get('power_diagnostics'):
            self._text('no_diagnostics', 480, 250,
                       'Energy diagnostics require the battery / exciter model.', 14)
            self.created_once = len(self.items)
            return

        cap = model.excitation_mode == 'capacitor'
        self._flow('charger_battery', [(770,145),(770,66),(70,66),(70,145)], TEAL)
        self._text('charger_battery_summary', 400, 70, '', 11, TEAL)
        self._flow('dc_charger', [(661,350),(661,262),(925,262),(925,195),(830,195)], TEAL)
        self._transfer('dc_charger_transfer', 860, 96, 'dc')
        self._fixed_line('dc_charger_leader', [(860,150),(860,190)])

        self._card('battery', 70, 145, 'BATTERY', 100)
        self._level('battery_level', 70, 190)
        self._card('boost', 220, 145, 'BOOST', 90)
        self._card('aux', 360, 145, 'AUX HV LINK', 110)
        self._level('aux_level', 360, 190)
        self._card('exciter', 500, 145, 'CAP + START' if cap else 'EXCITER', 100)
        if cap:
            self._level('capacitor_level', 500, 190)
        else:
            self._remember('exciter_hitbox', c.create_rectangle(
                *self._xy(450,145), *self._xy(550,245), fill='', outline='',
                tags=('energy_scene','exciter')))
            self._text('inverter_current', 500, 193, '', 12, PURPLE)
        self._card('charger', 770, 145, 'CHARGER', 120)
        self._text('charger_efficiency', 770, 191, '', 12)

        auxiliary = ((120,175,'battery_boost','dc'),
                     (265,305,'boost_aux','dc'),
                     (415,450,'aux_exciter','ac'))
        for a, b, name, kind in auxiliary:
            self._flow(name, [(a,177),(b,177)])
            self._transfer(name+'_transfer', (a+b)/2, 96, kind)
        for x, name in ((70,'battery'),(220,'boost'),(770,'charger')):
            self._flow(name+'_heat', [(x,245),(x,260)], HEAT)
            self._text(name+'_heat_text', x, 263, '', 11, HEAT)
        self._text('battery_summary', 750, 626, '', 11, MUTED)

        self._flow('aux_bus', [(500,245),(500,310),(419,310),(419,350)])
        self._flow('aux_bus_q', [(512,245),(512,322),(431,322),(431,350)], PURPLE, True)
        self._transfer('aux_bus_transfer', 585, 180, 'ac')
        self._flow('exciter_heat', [(548,245),(560,245),(560,322),(575,322)], HEAT)
        self._text('exciter_heat_text', 590, 327, '', 11, HEAT)

        centers = [56+121*i for i in range(8)]
        titles = ['LOAD','GEAR /\nBEARINGS','INDUCTION\nMACHINE','AC BUS',
                  'RECTIFIER','DC LINK','CHOPPER','BRAKE\nRESISTOR']
        keys = ['load','gear','machine','ac_bus','rectifier','dc_link','chopper','resistor']
        for x, key, title in zip(centers, keys, titles):
            self._card('main_'+key, x, 350, title)

        connection_names = ['load_gear','gear_machine','machine_bus','bus_rectifier',
                            'rectifier_dc','dc_chopper','chopper_resistor']
        for i, name in enumerate(connection_names):
            a, b = centers[i]+40, centers[i+1]-40
            self._flow(name, [(a,389),(b,389)])
            y = 470 if name == 'bus_rectifier' else 282
            kind = 'shaft' if i < 2 else ('ac' if i < 4 else 'dc')
            self._transfer(name+'_transfer', (a+b)/2, y, kind)
            if name == 'bus_rectifier':
                self._fixed_line(name+'_leader', [((a+b)/2,412),((a+b)/2,465)])
            else:
                self._fixed_line(name+'_leader', [((a+b)/2,347),((a+b)/2,386)])
            if kind == 'ac':
                self._flow(name+'_q', [(a,410),(b,410)], PURPLE, True)

        self._fixed_line('load_rope', [(56,383),(56,383)], MUTED, 2)
        self._remember('load_glyph', c.create_rectangle(
            *self._xy(47,383), *self._xy(65,393), fill=GOLD, outline='',
            tags=('energy_scene',)))
        self._remember('flux_ring', c.create_oval(
            *self._xy(centers[2]-18,395), *self._xy(centers[2]+18,425),
            outline='#2d415f', width=2, tags=('energy_scene',)))
        self._fixed_line('rotor', [(centers[2],410),(centers[2]+15,410)], GOLD, 3)
        self._level('dc_level', centers[5], 393)
        self._level('chopper_level', centers[6], 393)
        self._remember('chopper_pulse', c.create_oval(
            *self._xy(centers[6]+26,398), *self._xy(centers[6]+32,404),
            fill='#526479', outline='', tags=('energy_scene',)))

        for x, key in zip(centers, keys):
            if key in ('gear','machine','rectifier','resistor'):
                self._flow(key+'_component_heat', [(x-12,450),(x-12,480)], HEAT)
                self._text(key+'_component_heat_text', x, 485, '', 11, HEAT)
                if key == 'rectifier':
                    self._text('rectifier_note', x, 519, 'bridge / source', 11, MUTED)
            if key in ('load','gear','machine','dc_link'):
                self._flow(key+'_storage', [(x+29,450),(x+53,450),(x+53,550),(x,550)], TEAL)
                title = {'load':'Height energy','gear':'Kinetic energy',
                         'machine':'Magnetic field','dc_link':'DC capacitor'}[key]
                self._text(key+'_storage_title', x, 561, title, 11, TEAL)
                self._text(key+'_storage_text', x, 582, '', 11, TEAL)

        self._remember('field_panel', c.create_rectangle(
            *self._xy(750,520), *self._xy(938,615), fill='#142338',
            outline='#41556d', tags=('energy_scene',)))
        self._text('field_title', 844, 523, 'MACHINE MAGNETIC FIELD', 12, TEAL)
        for index in range(3):
            self._fixed_line('field_line_'+str(index), [(844,558),(844,558)], '#283c50', 1)
        self._text('field_value', 844, 580, '', 12, TEAL)
        self._text('field_note', 844, 598, 'Brightness: log scale', 11, MUTED)
        self._text('residual', 480, 647, '', 11, MUTED)
        self._text('sign_note', 480, 669,
                   'Signed battery current: + discharge / - charge. Ieq: averaged bridge fundamental equivalent.',
                   11, MUTED)

    def build_dynamic_items(self, model, readings):
        """Dynamic IDs are allocated by the scene builders; retain their count."""
        try:
            self.created_once = len(self.canvas.find_all())
        except AttributeError:
            self.created_once = len(self.items) + sum(len(v['particles'])+1 for v in self.flows.values())

    def _configure(self, item, **options):
        self.canvas.itemconfigure(item, **options)
        self.updates_last_frame += 1

    def _coords(self, item, *coords):
        self.canvas.coords(item, *coords)
        self.updates_last_frame += 1

    def _set_text(self, key, value, force=False):
        if key not in self.items:
            return
        if force or self.text_cache.get(key) != value:
            self._configure(self.items[key], text=value)
            self.text_cache[key] = value

    def _set_level(self, key, fraction, label, update_text):
        if key not in self.levels:
            return
        fraction = max(0.0, min(1.0, fraction))
        item, x, y = self.levels[key]
        self._coords(item, *self._xy(x-22,y+1), *self._xy(x-22+44*fraction,y+13))
        if update_text:
            self._set_text(key+'_label', label)

    @staticmethod
    def _transfer_strings(port):
        kind, power = port['kind'], port['power']
        arrow = '→' if power >= 0 else '←'
        if kind == 'ac':
            values = (f"{port['voltage']:.0f} V LL RMS\n{port['current']:.2f} A "
                      f"{'Ieq' if port['equivalent'] else 'RMS'}")
        elif kind == 'dc':
            values = f"{port['voltage']:.0f} V DC\n{port['current']:.2f} A DC"
        elif kind == 'shaft':
            values = f"{port['torque']:.2f} Nm\n{port['rpm']:.0f} rpm"
        else:
            values = f"{port['force']:.0f} N\n{port['velocity']*60:.1f} m/min"
        return values, f"{abs(power):.1f} W {arrow}", (f"Q {port['reactive']:+.0f} var ⇄"
                                                         if kind == 'ac' else None)

    def _update_transfer(self, key, port):
        values, power, reactive = self._transfer_strings(port)
        self._set_text(key+'_values', values)
        self._set_text(key+'_power', power)
        if reactive is not None:
            self._set_text(key+'_reactive', reactive)

    def update_telemetry(self, model, r, playing, update_text=True):
        self.telemetry = r
        self.updates_last_frame = 0
        if not r.get('power_diagnostics'):
            return
        d, p = r['power_diagnostics'], model.parameters
        comp, ports = d['components'], d['connections']
        cap = model.excitation_mode == 'capacitor'
        if update_text:
            limit=('CURRENT LIMIT' if r.get('vf_current_limited') else
                   'FLUX LIMIT' if r.get('vf_flux_limited') else
                   'POWER TRANSFER LIMIT' if r.get('power_transfer_limited') else 'NORMAL')
            frequency=(f" | f* {r['stator_frequency_command']:.1f}/{r['frequency_target']:.1f} Hz"
                       if r.get('frequency_command_applicable') else ' | frequency emergent')
            self._set_text('status',
                           f"{'RUNNING' if playing else 'PAUSED'} | {r.get('_time', model.state.time):.2f} s | "
                           f"{r.get('sequence_state','MANUAL')}{frequency} | {limit}")
            charge = ports['charger_battery']
            self._set_text('charger_battery_summary',
                           f"Charge: {charge['voltage']:.1f} V | {charge['current']:.2f} A | {charge['power']:.1f} W ←")
            self._set_text('battery_state', f"{r['battery_soc']:.1f}% SOC")
            self._set_text('boost_state', 'averaged')
            self._set_text('aux_state', 'C_aux')
            self._set_text('exciter_title', ('CAP + START' if r['startup_support'] else 'CAP BANK') if cap else 'EXCITER')
            self._set_text('exciter_state',
                           (f"K_CAP {'CLOSED' if r['k_cap'] else 'OPEN'}\nK_EXC {'CLOSED' if r['k_exc'] else 'OPEN'}"))
            self._set_text('inverter_current', f"{r['inverter_current']:.2f} A RMS")
            self._set_text('charger_state', 'ON - click' if r.get('charger_enabled', model.charger_enabled) else 'OFF - click')
            self._set_text('charger_efficiency', f"{p.charger_efficiency*100:.0f}% eff.")
            for name in ('battery','boost','charger'):
                self._set_text(name+'_heat_text', f"{comp[name]['heat']:.1f} W heat")
            self._set_text('battery_summary',
                           f"Battery {r['battery_voltage']:.2f} V | {r['battery_current']:+.2f} A | {r['battery_power']:+.1f} W")
            self._set_text('exciter_heat_text', f"{comp['exciter']['heat']:.1f} W exciter heat")
            self._set_text('main_load_state', f"{r['position']:.2f} m")
            self._set_text('main_gear_state', f"BRAKE\n{r['brake_physical_state']}")
            self._set_text('main_machine_state', f"{r['flux_magnitude']:.2g} Wb")
            self._set_text('main_ac_bus_state', f"{r['bus_frequency']:.1f} Hz")
            self._set_text('main_rectifier_state', r['main_dc_connection'])
            self._set_text('rectifier_note',
                           f"K_PRECHARGE {'CLOSED' if r['k_precharge'] else 'OPEN'} + "
                           f"R_PRE {p.dc_precharge_resistance:g} ohm ({r['dc_precharge_power']:.1f} W)\n"
                           f"K_MAIN {'CLOSED' if r['k_main'] else 'OPEN'}")
            self._set_text('main_dc_link_state', f"{r['dc_energy']:.1f} J")
            self._set_text('main_chopper_state',
                           f"CTRL {'ON' if r['chopper_enabled'] else 'OFF'}\n{r['chopper_duty']*100:.0f}% duty")
            self._set_text('main_resistor_state', f"{p.dc_brake_resistance:.0f} ohm")
            for name in ('dc_charger','battery_boost','boost_aux','aux_exciter','aux_bus'):
                self._update_transfer(name+'_transfer', ports[name])
            connection_names = ['load_gear','gear_machine','machine_bus','bus_rectifier',
                                'rectifier_dc','dc_chopper','chopper_resistor']
            for name in connection_names:
                self._update_transfer(name+'_transfer', ports[name])
            for key in ('gear','machine','rectifier','resistor'):
                item = comp[key]
                label = (f"Cu {item['copper']:.1f} W\nFe {item['core']:.1f} W"
                         if key == 'machine' else f"{item['heat']:.1f} W heat")
                self._set_text(key+'_component_heat_text', label)
            for key in ('load','gear','machine','dc_link'):
                item = comp[key]
                self._set_text(key+'_storage_text',
                               f"{item['storage_rate']:+.1f} W\n{item['energy']:.2f} J")
            self._set_text('residual',
                           f"Conservation residual {r['energy_residual']:+.6f} J   |   AC KCL {abs(d['kcl']):.2e} A")

        self._set_level('battery_level', r['battery_soc']/100,
                        f"{r['battery_remaining_wh']:.1f} Wh", update_text)
        self._set_level('aux_level', r['aux_voltage']/max(p.boost_target_voltage, 1e-9),
                        f"{r['aux_voltage']:.0f} V | {r['aux_energy']:.1f} J", update_text)
        if cap:
            cap_reference = max(1, .5*model.kernel.cac*400**2)
            self._set_level('capacitor_level', r['capacitor_energy']/cap_reference,
                            f"{r['capacitor_energy']:.2f} J", update_text)
        self._set_level('dc_level', r['dc_voltage']/max(p.chopper_threshold, 1),
                        f"{r['dc_voltage']:.0f} V", update_text)
        self._set_level('chopper_level', r['chopper_duty'], 'PWM', update_text)

    def _flow_values(self, r):
        d = r['power_diagnostics']
        comp, ports = d['components'], d['connections']
        values = {name: port['power'] for name, port in ports.items() if name in self.flows}
        values.update({name+'_q': port.get('reactive', 0.0)
                       for name, port in ports.items() if name+'_q' in self.flows})
        values.update({name+'_heat': comp[name]['heat'] for name in ('battery','boost','charger')})
        values['exciter_heat'] = comp['exciter']['heat']
        for key in ('gear','machine','rectifier','resistor'):
            values[key+'_component_heat'] = comp[key]['heat']
        for key in ('load','gear','machine','dc_link'):
            values[key+'_storage'] = comp[key]['storage_rate']
        return values

    def _point_on_path(self, points, fraction, reverse=False):
        pts = tuple(reversed(points)) if reverse else points
        lengths = [math.dist(a,b) for a,b in zip(pts, pts[1:])]
        distance = fraction*sum(lengths)
        for index, segment in enumerate(lengths):
            if distance <= segment:
                a, b = pts[index:index+2]
                q = distance/max(segment, 1e-12)
                return self._xy(a[0]+q*(b[0]-a[0]), a[1]+q*(b[1]-a[1]))
            distance -= segment
        return self._xy(*pts[-1])

    def update_animation(self, r, visual_time, playing=True):
        if not r.get('power_diagnostics'):
            return
        self.visual_time = visual_time
        values = self._flow_values(r)
        width, height = self.layout_signature
        particle_radius = 2.5*min(width/self.DESIGN_WIDTH, height/self.DESIGN_HEIGHT)
        for key, flow in self.flows.items():
            power = values.get(key, 0.0)
            active = abs(power) > .01
            arrow = 'both' if flow['reactive'] else ('first' if power < 0 else 'last')
            style = (active, arrow)
            if style != flow['style']:
                self._configure(flow['line'], fill=flow['color'] if active else '#45566a', arrow=arrow)
                flow['style'] = style
            density = (3 if flow['reactive'] or abs(power) >= 100 else
                       2 if abs(power) >= 10 else 1)
            for index, item in enumerate(flow['particles']):
                if not active or index >= density:
                    if flow['visible'][index]:
                        self._configure(item, state='hidden')
                        flow['visible'][index] = False
                    continue
                if flow['reactive']:
                    amplitude = .15+.27*min(1, math.log1p(abs(power))/math.log(1001))
                    fraction = .5+amplitude*math.sin(2*math.pi*visual_time*1.4+index*1.5)
                else:
                    speed = .22+.08*math.log1p(abs(power))
                    fraction = (visual_time*speed+index/3) % 1
                x, y = self._point_on_path(flow['points'], fraction,
                                            reverse=power < 0 and not flow['reactive'])
                self._coords(item, x-particle_radius, y-particle_radius,
                             x+particle_radius, y+particle_radius)
                if not flow['visible'][index]:
                    self._configure(item, state='normal')
                    flow['visible'][index] = True

        p = self.model.parameters
        sample_time = r.get('_time', visual_time)
        extrapolation = max(0.0, min(.05, visual_time-sample_time)) if playing else 0.0
        position = r['position']+r.get('velocity', 0.0)*extrapolation
        y = 383+33*math.log1p(max(0, position))/math.log1p(max(p.crane_height,1e-9))
        self._coords(self.items['load_rope'], *self._xy(56,383), *self._xy(56,y))
        self._coords(self.items['load_glyph'], *self._xy(47,y), *self._xy(65,y+10))
        x = 56+121*2
        angle = r.get('angle', 0.0)+r.get('omega', 0.0)*extrapolation
        self._coords(self.items['rotor'], *self._xy(x,410),
                     *self._xy(x+15*math.cos(angle),410+15*math.sin(angle)))

        flux = r['flux_magnitude']
        ratio = flux/max(p.exciter_flux_target, 1e-12)
        strength = min(1., math.log1p(1000*ratio)/math.log(1001))
        field_color = '#%02x%02x%02x' % (int(40+55*strength),
                                         int(60+160*strength), int(80+150*strength))
        ring_color = '#%02x%02x%02x' % (int(45+70*min(1,ratio)),
                                        int(65+150*min(1,ratio)), int(95+140*min(1,ratio)))
        self._configure(self.items['flux_ring'], outline=ring_color, width=2+3*min(1,ratio))
        # Flux angle is telemetry; this small extrapolation makes 50 Hz data
        # continuous at render rate without affecting the physics state.
        phase = r.get('flux_angle', 0.0)
        phase += 2*math.pi*r.get('bus_frequency', 0.0)*max(0.0, visual_time-sample_time)
        for index, radius in enumerate((38,29,20)):
            points = []
            for j in range(41):
                theta = 2*math.pi*j/40
                a, b = radius*math.cos(theta), 12*math.sin(theta)
                points.extend(self._xy(844+a*math.cos(phase)-b*math.sin(phase)*.3,
                                       558+a*math.sin(phase)*.3+b*math.cos(phase)))
            item = self.items['field_line_'+str(index)]
            self._coords(item, *points)
            self._configure(item, fill=field_color, width=1+2*strength)
        label = 'ZERO FIELD' if flux < 1e-12 else f'{flux:.3g} Wb | {100*ratio:.2g}%'
        self._set_text('field_value', label)
        pulse = GOLD if (visual_time*8)%1 < r['chopper_duty'] else '#526479'
        self._configure(self.items['chopper_pulse'], fill=pulse)
