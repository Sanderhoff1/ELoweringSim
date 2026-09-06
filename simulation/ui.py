"""Small standard-library UI: canvas animation, input fields, and history."""
from collections import deque
from dataclasses import fields, replace
import math
from pathlib import Path
import time
import tkinter as tk
from tkinter import ttk
from .parameters import Parameters
from .mechanical import MechanicalModel, Playback
from .dynamic_model import DynamicLoweringModel
from .external_model import ExternalLoweringModel, reviewed_parameters
from .energy_view import EnergyView
from .examples import small_hoist

DYNAMIC_FIELDS = {'stator_resistance', 'rotor_resistance', 'stator_leakage',
                  'rotor_leakage', 'saturation_flux', 'initial_flux',
                  'precharge_voltage', 'initial_shaft_rpm', 'ac_load_resistance',
                  'excitation_response'}
DYNAMIC_FIELDS |= {'dc_capacitance','dc_initial_voltage','rectifier_resistance','dc_brake_resistance'}
DYNAMIC_FIELDS |= {'chopper_threshold','chopper_band','chopper_response','chopper_max_duty',
                   'inverter_current_limit','inverter_output_resistance','inverter_idle_loss','inverter_min_dc_voltage'}
DYNAMIC_FIELDS |= {'battery_voltage','boost_target_voltage','boost_input_power_limit','boost_efficiency',
                   'boost_output_current_limit','boost_response','boost_voltage_gain'}
STEADY_FIELDS = {'peak_motor_torque', 'peak_slip', 'reference_volts_per_hz'}
REVIEWED_FIELDS = {'core_loss_resistance','external_supply_voltage','exciter_active_limit',
                   'exciter_absorption_limit','exciter_flux_target','startup_frequency',
                   'startup_flux_fraction','startup_dwell','startup_ramp'}


class Application:
    def __init__(self, root):
        self.root = root
        root.title("Emergency lowering — external flux exciter / passive rectifier")
        root.geometry(f"{min(1280, root.winfo_screenwidth()-80)}x{min(850, root.winfo_screenheight()-100)}")
        root.minsize(720, 480)
        self.model = ExternalLoweringModel()
        self.boost_enabled=tk.BooleanVar(value=False)
        self.converter_mode=tk.StringVar(value='External 400 V · reviewed')
        self.chopper_enabled=tk.BooleanVar(value=True)
        self.model.reset()
        self.model.motor_connected = True
        self.model.ideal_excitation = True
        self.model.capacitors_enabled = True
        self.clock = Playback(self.model)
        self.playing = False
        self.last_wall = time.perf_counter()
        self.history = deque(maxlen=1500)
        self.sample_steps = 0
        source = tk.PhotoImage(file=str(Path(__file__).with_name("assets") / "self_hoisting_crane.png"))
        self.crane_background = source.subsample(3, 3)
        # Playback stays outside both scrolling panes.
        toolbar = ttk.Frame(root, padding=8)
        toolbar.pack(side="top", fill="x")
        self.play_button = ttk.Button(toolbar, text="Play", command=self.toggle)
        self.play_button.pack(side="left", padx=4)
        ttk.Button(toolbar, text="Reset", command=self.reset).pack(side="left", padx=4)
        ttk.Label(toolbar, text="Speed ×").pack(side="left", padx=(12, 4))
        self.speed = tk.StringVar(value="1")
        selector = ttk.Combobox(toolbar, textvariable=self.speed, width=6, state="readonly", values=("0.05", "0.1", "0.25", "0.5", "1", "2", "5", "10"))
        selector.pack(side="left")
        selector.bind("<<ComboboxSelected>>", lambda event: self.sync())
        self.active_speed = 1.0
        self.released = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text="Release brake", variable=self.released, command=self.brake).pack(side="left", padx=12)
        body = ttk.Panedwindow(root, orient="horizontal")
        body.pack(fill="both", expand=True)
        sidebar = ttk.Frame(body, width=280)
        body.add(sidebar, weight=0)
        sidebar_tabs = ttk.Notebook(sidebar)
        sidebar_tabs.pack(fill='both',expand=True)
        explore = ttk.Frame(sidebar_tabs)
        advanced = ttk.Frame(sidebar_tabs)
        sidebar_tabs.add(explore,text='Explore')
        sidebar_tabs.add(advanced,text='Parameters')
        self.explore_canvas = tk.Canvas(explore, width=265, highlightthickness=0)
        explore_scroll = ttk.Scrollbar(explore, orient='vertical', command=self.explore_canvas.yview)
        explore_scroll.pack(side='right', fill='y')
        self.explore_canvas.pack(side='left', fill='both', expand=True)
        self.explore_canvas.configure(yscrollcommand=explore_scroll.set)
        controls = ttk.Frame(self.explore_canvas, padding=12)
        explore_window = self.explore_canvas.create_window(0, 0, window=controls, anchor='nw')
        controls.bind('<Configure>', lambda event: self.explore_canvas.configure(scrollregion=self.explore_canvas.bbox('all')))
        self.explore_canvas.bind('<Configure>', lambda event: self.explore_canvas.itemconfigure(explore_window, width=event.width))
        self.control_canvas = tk.Canvas(advanced, width=265, highlightthickness=0)
        control_scroll = ttk.Scrollbar(advanced, orient="vertical", command=self.control_canvas.yview)
        control_scroll.pack(side="right", fill="y")
        self.control_canvas.pack(side="left", fill="both", expand=True)
        self.control_canvas.configure(yscrollcommand=control_scroll.set)
        parameter_controls = ttk.Frame(self.control_canvas, padding=12)
        control_window = self.control_canvas.create_window(0, 0, window=parameter_controls, anchor="nw")
        parameter_controls.bind("<Configure>", lambda event: self.control_canvas.configure(scrollregion=self.control_canvas.bbox("all")))
        self.control_canvas.bind("<Configure>", lambda event: self.control_canvas.itemconfigure(control_window, width=event.width))
        ttk.Label(controls, text="EXPLORE THE FLOW", font=("Segoe UI", 12, "bold"),wraplength=230).pack(anchor="w")
        mode_selector=ttk.Combobox(controls,textvariable=self.converter_mode,state='readonly',
            values=('External 400 V · reviewed','5 · Legacy direct resistance','6 · Legacy ideal exciter','7 · Legacy DC-fed exciter'))
        mode_selector.pack(fill='x',pady=8)
        mode_selector.bind('<<ComboboxSelected>>',lambda event:self.change_power_stage())
        ttk.Label(controls,text='Default: small external exciter, passive rectifier, DC brake. Modes 5–7 are legacy comparisons.',wraplength=230).pack(anchor='w')
        self.dynamic_mode = tk.BooleanVar(value=True)
        ttk.Checkbutton(parameter_controls, text="Dynamic flux / capacitor model", variable=self.dynamic_mode, command=self.change_model).pack(anchor="w", pady=6)
        ttk.Label(controls,text='1. Choose an example',padding=(0,12,0,5)).pack(anchor='w')
        self.preset = tk.StringVar(value="External startup")
        demo_selector = ttk.Combobox(controls, textvariable=self.preset, state='readonly', values=('External startup','24 V startup','Exciter handover', 'Residual seed', 'Precharged bank', 'Zero seed'))
        demo_selector.pack(fill='x')
        self.guide = tk.StringVar()
        demo_selector.bind('<<ComboboxSelected>>',lambda event:self.update_guide())
        self.update_guide()
        ttk.Label(controls,textvariable=self.guide,wraplength=230).pack(anchor='w',pady=10)
        ttk.Button(controls, text="Start / restart this example", command=self.start_example).pack(fill='x', pady=4)
        ttk.Label(controls,text='External startup: zero speed, zero charge. The sequencer magnetizes, then releases the brake. Other examples are explicit comparisons.',wraplength=230,foreground='#666666').pack(anchor='w',pady=6)
        ttk.Label(controls,text='2. Try a change',padding=(0,12,0,5)).pack(anchor='w')
        self.connected = tk.BooleanVar(value=True)
        ttk.Checkbutton(parameter_controls, text="Connect machine to AC bus", variable=self.connected, command=self.connect_motor).pack(anchor="w", pady=6)
        self.excited = tk.BooleanVar(value=True)
        ttk.Checkbutton(parameter_controls,text='Legacy 24 V boost available',variable=self.boost_enabled,
                        command=self.toggle_boost).pack(anchor='w',pady=6)
        ttk.Label(parameter_controls,text='Phase 7 only; absent from the external 400 V topology.',wraplength=230).pack(anchor='w')
        ttk.Checkbutton(controls, text="Exciter ON", variable=self.excited, command=self.enable_excitation).pack(anchor="w", pady=6)
        ttk.Label(controls,text='You can also click the exciter in the diagram. Watch the field after it switches off.',wraplength=230).pack(anchor='w')
        self.capacitors = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Capacitors connected", variable=self.capacitors, command=self.connect_capacitors).pack(anchor="w", pady=(12,0))
        ttk.Label(controls,text='Changing this resets the run.',wraplength=230).pack(anchor='w')
        self.capacitance_value = tk.StringVar()
        ttk.Label(controls, textvariable=self.capacitance_value).pack(anchor='w', pady=(10,0))
        self.capacitance_slider = tk.Scale(
            controls, from_=0, to=30, resolution=0.1, orient='horizontal',
            showvalue=False, highlightthickness=0,
            command=lambda value: self.capacitance_value.set(f'Capacitance: {float(value):g} µF / branch'))
        self.capacitance_slider.pack(fill='x')
        self.capacitance_slider.bind('<ButtonRelease-1>', self.apply_capacitance)
        self.capacitance_slider.bind('<KeyRelease>', self.apply_capacitance)
        ttk.Label(controls,text='Release to apply. Dynamic runs reset. Each delta capacitor has this value.',wraplength=230).pack(anchor='w')
        self.sync_capacitance_slider()
        self.rectifier = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls,text='Rectifier + DC brake',variable=self.rectifier,
                        command=self.connect_rectifier).pack(anchor='w',pady=(12,0))
        ttk.Label(controls,text='Replaces the AC test load; resets run. Dynamic mode only.',wraplength=230).pack(anchor='w')
        self.resistance_value = tk.StringVar()
        ttk.Label(controls,textvariable=self.resistance_value).pack(anchor='w',pady=(8,0))
        self.resistance_slider = tk.Scale(controls,from_=50,to=2000,resolution=10,
            orient='horizontal',showvalue=False,highlightthickness=0,
            command=lambda value:self.resistance_value.set(f'DC brake: {float(value):g} ohm'))
        self.resistance_slider.pack(fill='x')
        self.resistance_slider.bind('<ButtonRelease-1>',self.apply_resistance)
        self.resistance_slider.bind('<KeyRelease>',self.apply_resistance)
        ttk.Label(controls,text='Release to apply live. Lower resistance draws more current at the same DC voltage.',wraplength=230).pack(anchor='w')
        self.sync_resistance_slider()
        ttk.Checkbutton(controls,text='Chopper enabled',variable=self.chopper_enabled,
                        command=self.toggle_chopper).pack(anchor='w',pady=(10,0))
        self.live_converter_sliders={}
        for key,title,low,high,resolution in (
            ('chopper_threshold','Chopper starts [V]',100,800,5),
            ('inverter_current_limit','Exciter limit [A RMS]',0.1,10,0.1),
            ('boost_target_voltage','Boost target [V]',100,750,5),
            ('boost_input_power_limit','Battery limit [W]',20,1000,10)):
            value=tk.StringVar()
            parent=parameter_controls if key.startswith('boost_') else controls
            ttk.Label(parent,textvariable=value).pack(anchor='w',pady=(8,0))
            slider=tk.Scale(parent,from_=low,to=high,resolution=resolution,
                orient='horizontal',showvalue=False,highlightthickness=0,
                command=lambda number,v=value,t=title:v.set(f'{t}: {float(number):g}'))
            slider.pack(fill='x')
            slider.bind('<ButtonRelease-1>',lambda event,k=key:self.apply_converter_setting(k))
            slider.bind('<KeyRelease>',lambda event,k=key:self.apply_converter_setting(k))
            self.live_converter_sliders[key]=(slider,value,title,low,high)
        self.sync_converter_sliders()
        ttk.Label(controls,text='3. Look for the difference',padding=(0,12,0,5)).pack(anchor='w')
        ttk.Label(controls,text='Is the field growing or fading?\nAre the capacitors charging?\nIs the load actually slowing down?',wraplength=230).pack(anchor='w')
        ttk.Label(parameter_controls, text="Illustrative inputs — replace with measured values.", wraplength=230).pack(anchor="w", pady=8)
        self.inputs = {}
        self.input_frames = {}
        self.parameter_frame = ttk.Frame(parameter_controls)
        self.parameter_frame.pack(fill='x')
        for item in fields(Parameters):
            meta = item.metadata
            frame = ttk.Frame(self.parameter_frame)
            self.input_frames[item.name] = frame
            ttk.Label(frame, text=f"{item.name} [{meta['unit']}] · {meta['status']}").pack(anchor="w", pady=(7, 0))
            variable = tk.StringVar(value=str(getattr(self.model.parameters, item.name)))
            ttk.Entry(frame, textvariable=variable).pack(fill="x")
            ttk.Label(frame, text=meta['meaning'], wraplength=230, foreground="#555555").pack(anchor="w")
            self.inputs[item.name] = variable
        self.show_parameters()
        ttk.Button(parameter_controls, text="Apply inputs", command=self.apply).pack(fill="x", pady=10)
        self.message = tk.StringVar(value="Dynamic inputs and circuit connections reset the run. Exciter and brake switches act live.")
        ttk.Label(parameter_controls, textvariable=self.message, wraplength=230).pack(anchor="w")
        ttk.Label(controls,textvariable=self.message,wraplength=230,foreground='#666666').pack(anchor='w',pady=12)
        self.view_tabs = ttk.Notebook(body)
        body.add(self.view_tabs, weight=1)
        overview = ttk.Frame(self.view_tabs)
        view = ttk.Frame(self.view_tabs)
        self.view_tabs.add(overview,text='Energy flow')
        self.view_tabs.add(view,text='Details & plots')
        self.flow_canvas = tk.Canvas(overview,background='#101b2c',highlightthickness=0)
        overview.rowconfigure(0, weight=1)
        overview.columnconfigure(0, weight=1)
        self.flow_canvas.grid(row=0,column=0,sticky='nsew')
        flow_y = ttk.Scrollbar(overview,orient='vertical',command=self.flow_canvas.yview)
        flow_y.grid(row=0,column=1,sticky='ns')
        flow_x = ttk.Scrollbar(overview,orient='horizontal',command=self.flow_canvas.xview)
        flow_x.grid(row=1,column=0,sticky='ew')
        self.flow_canvas.configure(yscrollcommand=flow_y.set,xscrollcommand=flow_x.set)
        self.energy_view = EnergyView(self.flow_canvas,self.toggle_exciter_from_diagram)
        view.rowconfigure(0, weight=1)
        view.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(view, background="#101b2c", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(view, orient="vertical", command=self.canvas.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(view, orient="horizontal", command=self.canvas.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        root.bind_all("<MouseWheel>", self.scroll)
        self.tick()

    def update_guide(self):
        self.guide.set({
            'External startup':'Press Start. The external 400 V supply builds flux at low frequency with the brake held. The brake releases after flux qualifies, then frequency ramps to 50 Hz.',
            '24 V startup':'Brake stays held. Let the boost charge the DC bus, enable the exciter, then release the brake to explore lowering. No automatic startup sequencer yet.',
            'Exciter handover':'Let the exciter build the magnetic field. Then switch it OFF and watch what remains.',
            'Residual seed':'Start with a tiny magnetic seed and no exciter. Watch for voltage and field to grow.',
            'Precharged bank':'Start with energy in the capacitors and no exciter. Watch that energy enter the machine.',
            'Zero seed':'No capacitor charge, no magnetic seed, no exciter. The load can move while the electrical system stays dark.'
        }[self.preset.get()])
        if self.converter_mode.get().startswith('7') and self.preset.get()=='Exciter handover':
            self.guide.set('Starts with 600 V DC precharge. Keep the exciter ON for a working baseline. Switch it OFF later to test capacitor-only excitation.')

    def configure_power_stage(self):
        if isinstance(self.model,ExternalLoweringModel):
            self.model.chopper_enabled=self.chopper_enabled.get()
            self.model.boost_enabled=False
            self.boost_enabled.set(False)
            return
        if self.converter_mode.get().startswith('External'):
            self.model.chopper_active=self.model.dc_exciter=self.model.boost_enabled=False
            return
        dynamic=isinstance(self.model,DynamicLoweringModel)
        stage=int(self.converter_mode.get()[0])
        self.model.chopper_active=dynamic and self.model.rectifier_enabled and stage>=6
        self.model.dc_exciter=dynamic and self.model.rectifier_enabled and stage==7
        self.model.chopper_enabled=self.chopper_enabled.get()
        self.model.boost_enabled=dynamic and self.model.dc_exciter and self.boost_enabled.get()

    def change_power_stage(self):
        if (self.converter_mode.get().startswith('7') and self.boost_enabled.get()
                and self.model.parameters.boost_target_voltage>self.model.parameters.chopper_threshold-20):
            self.converter_mode.set('7 · DC-fed exciter' if getattr(self.model,'dc_exciter',False)
                                    else '6 · Chopper + ideal exciter' if getattr(self.model,'chopper_active',False)
                                    else '5 · Direct resistance')
            self.message.set('Lower the boost target at least 20 V below chopper start before selecting Phase 7.')
            return
        self.sync()
        self.dynamic_mode.set(True)
        self.rectifier.set(True)
        self.capacitors.set(True)
        if self.model.parameters.capacitor_capacitance<=0:
            self.model.parameters=replace(self.model.parameters,capacitor_capacitance=6)
            self.inputs['capacitor_capacitance'].set('6')
        self.change_model()
        self.update_guide()
        self.message.set('Power stage changed; run reset using the displayed parameters. Select External startup to restore the reviewed example.')

    def toggle_chopper(self):
        self.sync()
        self.model.chopper_enabled=self.chopper_enabled.get()
        self.message.set('Chopper command changed live; duty responds over time. Active in Phases 6–7.')

    def toggle_boost(self):
        if not self.dynamic_mode.get() or not self.converter_mode.get().startswith('7'):
            self.boost_enabled.set(False)
            self.message.set('Choose Phase 7 for 24 V boost support.')
            return
        if not self.valid_dc_configuration():
            self.boost_enabled.set(self.model.boost_enabled)
            return
        self.sync()
        self.model.boost_enabled=self.boost_enabled.get()
        self.message.set('24 V boost availability changed live; charge, motion and energy history retained.')

    def sync_converter_sliders(self):
        for key,(slider,label,title,low,high) in self.live_converter_sliders.items():
            value=getattr(self.model.parameters,key)
            slider.configure(from_=min(low,value),to=max(high,value))
            slider.set(value)
            label.set(f'{title}: {value:g}')

    def apply_converter_setting(self,key):
        value=float(self.live_converter_sliders[key][0].get())
        parameters=replace(self.model.parameters,**{key:value})
        if not self.valid_dc_configuration(parameters):
            self.sync_converter_sliders()
            return
        self.sync()
        self.model.parameters=parameters
        self.inputs[key].set(str(value))
        self.message.set('Converter setting applied live; energy and motion retained.')

    def sync_capacitance_slider(self):
        value = self.model.parameters.capacitor_capacitance
        # Preserve larger values entered in Parameters rather than clipping them.
        self.capacitance_slider.configure(to=max(30, value))
        self.capacitance_slider.set(value)
        self.capacitance_value.set(f'Capacitance: {value:g} µF / branch')

    def sync_resistance_slider(self):
        value = self.model.parameters.dc_brake_resistance
        self.resistance_slider.configure(from_=min(50,value),to=max(2000,value))
        self.resistance_slider.set(value)
        self.resistance_value.set(f'DC brake: {value:g} ohm')

    def apply_resistance(self,event=None):
        value = float(self.resistance_slider.get())
        if value == self.model.parameters.dc_brake_resistance:
            return
        self.sync()
        self.model.parameters = replace(self.model.parameters,dc_brake_resistance=value)
        self.inputs['dc_brake_resistance'].set(str(value))
        self.message.set(f'DC brake set to {value:g} ohm; applied live.'
                         if self.dynamic_mode.get() and self.rectifier.get()
                         else f'DC brake set to {value:g} ohm; enable the dynamic rectifier path to use it.')

    def connect_rectifier(self):
        if not self.dynamic_mode.get():
            self.rectifier.set(False)
            self.message.set('Select the dynamic model in Parameters to use the DC path.')
            return
        if not self.valid_dc_configuration():
            self.rectifier.set(self.model.rectifier_enabled)
            return
        self.sync()
        self.model.rectifier_enabled = self.rectifier.get()
        self.configure_power_stage()
        self.reset()
        self.message.set('DC path enabled; AC test load removed. Run reset.' if self.rectifier.get()
                         else 'AC test load restored. Run reset.')

    def apply_capacitance(self, event=None):
        value = float(self.capacitance_slider.get())
        if not self.valid_dc_configuration(replace(self.model.parameters,capacitor_capacitance=value)):
            self.sync_capacitance_slider()
            return
        if value == self.model.parameters.capacitor_capacitance:
            return
        self.sync()
        self.model.parameters = replace(self.model.parameters, capacitor_capacitance=value)
        self.inputs['capacitor_capacitance'].set(str(value))
        if self.dynamic_mode.get():
            self.reset()
        self.message.set(f'Capacitance set to {value:g} µF per delta branch.'
                         + (' Run reset.' if self.dynamic_mode.get() else ' Applied live.'))

    def start_example(self):
        self.load_demo()
        self.view_tabs.select(0)
        self.toggle()

    def toggle_exciter_from_diagram(self):
        self.excited.set(not self.excited.get())
        self.enable_excitation()

    def show_parameters(self):
        for name, frame in self.input_frames.items():
            frame.pack_forget()
            hidden = STEADY_FIELDS if self.dynamic_mode.get() else DYNAMIC_FIELDS
            if not isinstance(self.model,ExternalLoweringModel):
                hidden=hidden | REVIEWED_FIELDS
            if isinstance(self.model,ExternalLoweringModel):
                hidden = hidden | {'battery_voltage','boost_target_voltage','boost_input_power_limit','boost_efficiency','boost_output_current_limit','boost_response','boost_voltage_gain','inverter_min_dc_voltage','ac_load_resistance'}
            if name not in hidden:
                frame.pack(fill='x')

    def change_model(self):
        if not self.valid_dc_configuration():
            self.dynamic_mode.set(isinstance(self.model,(DynamicLoweringModel,ExternalLoweringModel)))
            return
        self.sync()
        model_type = DynamicLoweringModel if self.dynamic_mode.get() else MechanicalModel
        if self.dynamic_mode.get() and self.converter_mode.get().startswith('External'):
            model_type=ExternalLoweringModel
        self.model = model_type(self.model.parameters)
        self.model.rectifier_enabled = self.rectifier.get() if self.dynamic_mode.get() else False
        self.configure_power_stage()
        if not self.dynamic_mode.get():
            self.rectifier.set(False)
        self.model.motor_connected = self.connected.get()
        self.model.ideal_excitation = True
        self.model.inverter_enabled = self.excited.get()
        self.model.capacitors_enabled = self.capacitors.get()
        self.model.brake_released = self.released.get()
        self.clock = Playback(self.model)
        self.show_parameters()
        self.reset()
        self.message.set('Model changed; run reset. Dynamic and steady-state motor parameters differ.')

    def load_demo(self):
        # Explicit demonstrations, not equipment specifications. A spinning
        # start provides a repeatable opportunity for a seed to grow.
        self.sync()
        self.update_guide()
        self.playing = False
        name = self.preset.get()
        if name=='External startup':
            self.converter_mode.set('External 400 V · reviewed')
            self.model.parameters=reviewed_parameters()
            for key,variable in self.inputs.items():
                variable.set(str(getattr(self.model.parameters,key)))
            for flag in (self.dynamic_mode,self.connected,self.capacitors,self.rectifier,self.excited,self.chopper_enabled):
                flag.set(True)
            self.released.set(False)
            self.boost_enabled.set(False)
            self.change_model()
            self.play_button.configure(text='Play')
            self.message.set('From rest, no precharge or magnetic seed. Startup releases the brake only after flux qualifies. Parameters are estimates.')
            return
        if self.converter_mode.get().startswith('External'):
            self.converter_mode.set('7 · Legacy DC-fed exciter' if name=='Exciter handover' else '5 · Legacy direct resistance')
        if name=='24 V startup':
            self.converter_mode.set('7 · DC-fed exciter')
        self.boost_enabled.set(name in ('24 V startup','Exciter handover'))
        self.chopper_enabled.set(True)
        p = small_hoist(initial_shaft_rpm=0 if name=='24 V startup' else 1530,
                       initial_flux=0.005 if name=='Residual seed' else 0.0,
                       precharge_voltage=200 if name=='Precharged bank' else 0.0,
                       chopper_threshold=500 if self.converter_mode.get().startswith('6') else 560,
                       dc_initial_voltage=600 if name=='Exciter handover' and self.converter_mode.get().startswith('7') else 0)
        for key, variable in self.inputs.items():
            variable.set(str(getattr(p, key)))
        self.dynamic_mode.set(True)
        self.connected.set(True)
        self.capacitors.set(True)
        if self.converter_mode.get().startswith('7'):
            self.rectifier.set(True)
        self.excited.set(name=='Exciter handover')
        self.released.set(name!='24 V startup')
        self.model.parameters = p
        self.change_model()
        self.playing = False
        self.play_button.configure(text='Play')
        self.message.set(f'{name}: estimated 0.9 kW / 4-pole hoist, 300 kg, 200 m. Moving start: 1530 RPM. '
                         + ('Keep exciter ON first; switching OFF tests capacitor-only operation.' if self.excited.get() else 'Exciter starts OFF.'))
        if name=='24 V startup':
            self.message.set('Empty DC bus; brake held; exciter OFF. Boost charges first. Then enable excitation and release the brake manually.')

    def scroll(self, event):
        widget = event.widget
        while widget is not None:
            if widget in (self.control_canvas, self.explore_canvas):
                widget.yview_scroll(-1 if event.delta > 0 else 1, "units")
                return "break"
            if widget in (self.canvas, self.flow_canvas):
                scroll = widget.xview_scroll if event.state & 1 else widget.yview_scroll
                scroll(-1 if event.delta > 0 else 1, "units")
                return "break"
            widget = getattr(widget, 'master', None)

    def sample(self):
        self.sample_steps += 1
        if self.sample_steps % 25 == 0:
            r = self.model.readings()
            self.history.append((self.model.state.time, r['velocity'], r['acceleration'], r['gravity_power'], r['brake_capacity'], r['motor_torque'], r['slip'], r['electrical_export'], r['rotor_loss'], r['line_voltage'], r['inverter_current'], r['inverter_reactive_supply'], r['capacitor_reactive_supply'], r['capacitor_line_current'], r.get('flux_magnitude',0), r.get('capacitor_energy',0), r.get('bus_frequency',self.model.parameters.supply_frequency)))

            self.history[-1] += tuple(r.get(key,0) for key in
                ('dc_voltage','dc_brake_power','dc_energy','rectifier_power',
                 'chopper_duty','inverter_dc_power','inverter_loss',
                 'battery_power','boost_power','boost_loss'))

    def sync(self):
        now = time.perf_counter()
        if self.playing:
            self.clock.advance(now-self.last_wall, self.active_speed, self.sample,
                               max_steps=(10 if self.model.rectifier_enabled else 50) if self.dynamic_mode.get() else 2000)
        self.last_wall = now
        self.active_speed = float(self.speed.get())

    def apply(self):
        try:
            parameters = Parameters(**{name: float(var.get()) for name, var in self.inputs.items()})
        except ValueError as error:
            self.message.set(str(error))
            return
        if not self.valid_dc_configuration(parameters):
            return
        self.sync()
        old = self.model.parameters
        reset_needed = self.dynamic_mode.get() or any(getattr(parameters, key) != getattr(old, key) for key in ('mass', 'radius', 'inertia', 'crane_height'))
        self.model.parameters = parameters
        self.sync_capacitance_slider()
        self.sync_resistance_slider()
        self.sync_converter_sliders()
        if reset_needed:
            self.reset()
        self.message.set("Inputs applied; run reset." if reset_needed else "Inputs applied at current simulation time.")

    def brake(self):
        self.sync()
        if isinstance(self.model,ExternalLoweringModel):
            self.model.startup_enabled=False
            self.model.startup_status='MANUAL BRAKE'
            self.message.set('Manual brake control selected; Reset restores automatic startup.')
        self.model.brake_released = self.released.get()

    def connect_motor(self):
        if isinstance(self.model,ExternalLoweringModel) and not self.connected.get():
            self.connected.set(True)
            self.message.set('The reviewed topology keeps the machine connected. Use a legacy comparison for disconnection.')
            return
        self.sync()
        self.model.motor_connected = self.connected.get()
        if self.dynamic_mode.get():
            self.reset()
            self.message.set('Machine connection changed; dynamic run reset to consistent initial conditions.')

    def enable_excitation(self):
        if not self.valid_dc_configuration():
            self.excited.set(self.model.inverter_enabled)
            return
        self.sync()
        self.model.inverter_enabled = self.excited.get()

    def connect_capacitors(self):
        if not self.valid_dc_configuration():
            self.capacitors.set(self.model.capacitors_enabled)
            return
        self.sync()
        self.model.capacitors_enabled = self.capacitors.get()
        if self.dynamic_mode.get():
            self.reset()
            self.message.set('Capacitor connection changed; dynamic run reset. Exciter switch remains live.')

    def valid_dc_configuration(self, parameters=None):
        p = parameters or self.model.parameters
        if self.dynamic_mode.get() and self.converter_mode.get().startswith('External'):
            if not self.rectifier.get() or not self.capacitors.get() or p.capacitor_capacitance<=0 or not self.connected.get():
                self.message.set('Reviewed topology requires the machine, AC bank and passive DC path connected.')
                return False
        if (self.dynamic_mode.get() and self.converter_mode.get().startswith('7') and self.boost_enabled.get()
                and p.boost_target_voltage>p.chopper_threshold-20):
            self.message.set('Keep the boost target at least 20 V below chopper start. Lower the boost target or raise chopper start first.')
            return False
        if (self.dynamic_mode.get() and self.converter_mode.get().startswith('7')
                and (not self.rectifier.get() or not self.capacitors.get() or p.capacitor_capacitance<=0)):
            self.message.set('Phase 7 needs the DC path and AC capacitors. Select Phase 5 or 6 for earlier comparisons.')
            return False
        if (self.dynamic_mode.get() and self.rectifier.get() and not self.excited.get()
                and (not self.capacitors.get() or p.capacitor_capacitance<=0)):
            self.message.set('Passive DC operation needs nonzero AC capacitance in this averaged model. Keep the bank connected, or turn off the DC path first.')
            return False
        return True

    def toggle(self):
        self.sync()
        self.playing = not self.playing
        self.play_button.configure(text="Pause" if self.playing else "Play")

    def reset(self):
        if isinstance(self.model,ExternalLoweringModel):
            self.model.startup_enabled=True
        self.model.reset()
        self.released.set(self.model.brake_released)
        self.sync_capacitance_slider()
        self.sync_resistance_slider()
        self.sync_converter_sliders()
        self.clock.pending = 0
        self.history.clear()
        self.sample_steps = 0
        self.last_wall = time.perf_counter()

    def tick(self):
        try:
            self.sync()
        except (ValueError, OverflowError) as error:
            self.playing = False
            self.play_button.configure(text='Play')
            self.message.set(f'Simulation paused: {error}')
        self.draw()
        self.root.after(16, self.tick)

    def draw(self):
        self.released.set(self.model.brake_released)
        if self.view_tabs.index(self.view_tabs.select())==0:
            self.energy_view.draw(self.model,self.model.readings(),self.history,self.playing)
            return
        c, s, r = self.canvas, self.model.state, self.model.readings()
        c.delete("all")
        # The canvas has a deliberate minimum content width. Smaller windows
        # scroll horizontally instead of collapsing sections onto each other.
        width = max(c.winfo_width(), 1040)
        def label(x, y, text, color="#e4efff", size=11, anchor="nw"):
            c.create_text(x, y, text=text, fill=color, font=("Segoe UI", size), anchor=anchor)
        label(22, 15, f"t = {s.time:8.3f} s    playback {self.active_speed:g}×    {'RUNNING' if self.playing else 'PAUSED'}", size=15)
        label(22, 49, f"Descent {r['velocity']:.3f} m/s    acceleration {r['acceleration']:.3f} m/s²    shaft {r['rpm']:.1f} RPM" + (f"   lag {self.clock.pending:.1f} s" if self.clock.pending>0.2 else ''))
        self.draw_crane(label)
        # Telemetry owns the column to the right of the 700 px crane scene.
        info_x = 640
        label(info_x, 90, "LANDED — Reset to restart" if s.grounded else "LOWERING BAY", color="#f5bc57", size=13)
        label(info_x, 124, f"Clearance: {r['clearance']:.3f} m\nTravel: {s.position:.3f} / {self.model.parameters.crane_height:g} m\nBrake command: {'RELEASE' if self.model.brake_released else 'APPLY'}\nAvailable brake torque: {r['brake_capacity']:.1f} N m")
        c.create_rectangle(info_x, 215, info_x+350, 229, fill="#293140", outline="")
        c.create_rectangle(info_x, 215, info_x+350*(r['brake_capacity']/max(self.model.parameters.brake_torque, 1e-9)), 229, fill="#f5bc57", outline="")
        label(info_x, 250, f"Shaft angle: {s.angle:.2f} rad\nShaft speed: {s.omega:.2f} rad/s\nPotential energy*: {r['potential_energy']:.1f} J\nKinetic energy: {r['kinetic_energy']:.1f} J\nGravity power: {r['gravity_power']:.1f} W\nBrake dissipation: {r['brake_power']:.1f} W\nViscous dissipation: {r['friction_power']:.1f} W")
        label(info_x, 410, f"Impact: {s.impact_speed:.2f} m/s · {s.impact_energy:.1f} J" if s.grounded else "*Energy relative to starting height", color="#93a3ba", size=9)

        # Electrical telemetry occupies its own row below the illustration.
        connected = self.model.motor_connected
        dynamic = self.dynamic_mode.get()
        mode_color = '#4ee1bd' if r['motor_mode'] == 'GENERATING' else '#f5bc57'
        label(22, 455, f"INDUCTION MACHINE · {r['motor_mode']}", color=mode_color, size=12)
        slip_text = f"{100*r['slip']:.2f}%" if r.get('slip_valid',True) else 'undefined (no rotating voltage)'
        label(22, 488, f"{'Bus field speed' if dynamic else 'Synchronous speed'}: {r['synchronous_rpm']:.1f} RPM\nSlip: {slip_text}\nElectromagnetic torque: {r['motor_torque']:.2f} N m")
        label(400, 488, f"{'Machine terminal export' if dynamic else 'Export to AC sink'}: {r['electrical_export']:.1f} W\nMotor shaft power: {r['motor_shaft_power']:.1f} W\nRotor heat loss: {r['rotor_loss']:.1f} W")
        label(22, 565, "Export: positive = generating; negative = power drawn from source. Torque: positive = lowering.", color='#93a3ba', size=10)
        label(22, 590, 'Dynamic flux and capacitor voltage; power includes changes in stored electrical energy.' if dynamic else "Beyond peak slip: available torque falls as slip grows." if r['beyond_peak'] else "Ideal supply establishes excitation instantly; no electrical transients modeled.", color='#93a3ba', size=10)
        label(22, 630, 'EXTERNAL 400 V · SMALL FLUX EXCITER' if r.get('external_exciter') else 'DC-FED EXCITATION · '+r['inverter_status'] if r.get('dc_exciter') else "IDEAL EXCITATION · ON" if (dynamic or connected) and self.model.inverter_enabled else "IDEAL EXCITATION · OFF / DISCONNECTED", color='#4ee1bd', size=12)
        voltage_note = 'V RMS-equivalent' if dynamic else 'V RMS'
        field_note = f"Flux: {r.get('flux_magnitude',0):.4f} Wb turn" if dynamic else f"Effective peak torque: {r['effective_peak_torque']:.1f} N m"
        frequency_note = f"Bus frequency: {r.get('bus_frequency',0):.2f} Hz (vector estimate)" if dynamic else f"Frequency: {self.model.parameters.supply_frequency:g} Hz (fixed setpoint)"
        label(22, 660, f"AC line voltage: {r['line_voltage']:.2f} {voltage_note}\n{frequency_note}\nExciter setting: {self.model.parameters.supply_frequency:g} Hz, {self.model.parameters.volts_per_hz:g} V/Hz\n{field_note}")
        label(470, 660, f"Inverter current: {r['inverter_current']:.3f} A RMS\nNet inverter VAR: {r['inverter_reactive_supply']:+.1f} var\nInverter real power: {r['inverter_real_power']:.1f} W\nMachine line current: {r['machine_line_current']:.3f} A RMS")
        label(22, 756, f"DC-fed: {r['inverter_dc_power']:+.1f} W from DC · {r['inverter_loss']:.1f} W loss · ceiling {r['inverter_voltage_limit']:.1f} V LL · limit {self.model.parameters.inverter_current_limit:g} A" if r.get('dc_exciter') else f"External supply {r['external_supply_power']:.1f} W · converter loss {r['inverter_loss']:.1f} W · limited active power; passive regeneration" if r.get('external_exciter') else 'Ideal inverter uses an external energy source/sink; OFF means zero inverter current.' if dynamic else "Inverter VAR: positive supplies, negative absorbs. Real watts use the ideal P boundary.", color='#93a3ba', size=10)
        label(22, 795, "PARALLEL AC CAPACITORS · DELTA", color='#4ee1bd', size=12)
        label(22, 826, f"Bank: {'CONNECTED' if self.model.capacitors_enabled else 'DISCONNECTED'}\nCapacitance: {self.model.parameters.capacitor_capacitance:g} µF per branch\nCapacitor supply: {r['capacitor_reactive_supply']:.1f} var\nCapacitor line current: {r['capacitor_line_current']:.3f} A RMS")
        capacitor_note = (f"Capacitor energy: {r.get('capacitor_energy',0):.3f} J\nMagnetic energy: {r.get('magnetic_energy',0):.3f} J\nAC test load: {r.get('load_power',0):.2f} W\nEnergy balance error: {r.get('energy_residual',0):.4g} J" if dynamic else f"Machine VAR demand: {r['machine_reactive_demand']:.1f} var\nCompensation: {100*r['compensation_fraction']:.1f}%\nFull compensation C: {r['matching_capacitance']:.1f} µF/branch\nVoltage held by the ideal inverter")
        label(470, 826, capacitor_note)
        label(22, 925, 'Self-excitation depends on speed, capacitance, seed, saturation and loading; no voltage clamp when OFF.' if dynamic else "Steady-state compensation only: capacitor-only self-excitation and switching transients are not modeled.", color='#93a3ba', size=10)
        system_y = 965
        dc_on = r.get('rectifier_enabled',False)
        label(22, system_y, "SYSTEM · DC-fed exciter / controlled chopper" if r.get('dc_exciter') else "SYSTEM · averaged rectifier / DC brake active" if dc_on else "SYSTEM · AC test-load mode", size=12)
        row1, row2, row3 = system_y+34, system_y+85, system_y+136
        boxes = [(22, row1, 'Load / drum', True), (180, row1, 'Induction machine', connected), (338, row1, 'AC bus', connected), (496, row1, 'Excitation inverter', self.model.inverter_enabled), (338, row2, 'Delta capacitors', self.model.capacitors_enabled), (22, row3, '3-phase rectifier', dc_on), (180, row3, 'DC bus', dc_on), (338, row3, 'Direct DC path', dc_on), (496, row3, 'Brake resistor', dc_on), (22, row2, '24 V', False), (180, row2, 'Bootstrap', False), (680, row2, 'AC resistive load' if dynamic else 'Ideal P source/sink', not dc_on)]
        if r.get('external_exciter'):
            boxes=boxes[:9]+[(680,row1,'External 400 V',self.model.inverter_enabled)]
            c.create_line(680,row1+21,636,row1+21,fill='#ffc36a',arrow='last',width=2)
        else:
            c.create_line(460, row1+42, 460, row2-4, 750, row2-4, 750, row2, fill=mode_color if connected else '#687384', arrow='both', width=2)
        for points in [(162,row1+21,180,row1+21),(320,row1+21,338,row1+21),(478,row1+21,496,row1+21),(408,row1+42,408,row2),(350,row1+42,350,row2-5,12,row2-5,12,row3+21,22,row3+21),(162,row3+21,180,row3+21),(320,row3+21,338,row3+21),(478,row3+21,496,row3+21),(162,row2+21,180,row2+21),(250,row2+42,250,row3)]:
            if r.get('external_exciter') and points in ((162,row2+21,180,row2+21),(250,row2+42,250,row3)):
                continue
            c.create_line(*points, fill="#687384", arrow="last")
        for x,y,title,active in boxes:
            if r.get('external_exciter') and title in ('24 V','Bootstrap'):
                title='External 400 V' if title=='24 V' else 'Exciter supply'
                active=self.model.inverter_enabled
            elif title in ('24 V','Bootstrap'):
                active=r.get('boost_enabled',False)
                title='24 V boost' if title=='Bootstrap' else title
            if title=='Direct DC path' and r.get('chopper_active'):
                title='Brake chopper'
            c.create_rectangle(x,y,x+140,y+42, fill="#214a50" if active else '#293140', outline="#4ee1bd" if active else '#4c5666')
            label(x+70,y+21,title,color="#e4efff" if active else '#8c96a8',anchor="center",size=9)
        c.create_line(496, row1+21, 478, row1+21,
                      fill='#4ee1bd' if connected and self.model.inverter_enabled else '#687384',
                      arrow='first' if r['inverter_reactive_supply'] < 0 else 'last', width=2)
        c.create_line(408, row2, 408, row1+42,
                      fill='#4ee1bd' if r['capacitor_reactive_supply'] > 0 else '#687384', arrow='last', width=2)
        if dc_on:
            label(22,system_y+190,f"DC bus: {r['dc_voltage']:.1f} V / {r['dc_energy']:.2f} J    Brake heat: {r['dc_brake_power']:.1f} W\nBridge input: {r['rectifier_power']:.1f} W    Duty: {100*r['chopper_duty']:.1f}% / command {100*r['chopper_command']:.1f}%")
            label(22,system_y+238,f"External supply: {r['external_supply_power']:.1f} W · core heat: {r['core_loss']:.1f} W · startup {r['startup_status']}" if r.get('external_exciter') else f"24 V: {r.get('battery_power',0):.1f} W / {r.get('battery_energy',0)/3600:.3f} Wh used · boost {r.get('boost_status','OFF')} · loss {r.get('boost_loss',0):.1f} W")
        history_y = system_y+285
        label(22, history_y, "HISTORY · last 75 simulated seconds · separate auto-scaled axes", size=11)
        for index, title, color in [(1, 'Speed [m/s]', '#4ee1bd'), (2, 'Acceleration [m/s²]', '#e6ae54'), (3, 'Gravity power [W]', '#a5b9ff'), (4, 'Brake capacity [N m]', '#ee986c'), (5, 'Motor torque [N m]', '#4ee1bd'), (6, 'Slip [1]', '#e6ae54'), (7, 'AC export [W]', '#a5b9ff'), (8, 'Rotor loss [W]', '#ee986c'), (9, 'AC voltage [V]', '#4ee1bd'), (10, 'Inverter [A]', '#e6ae54'), (11, 'Inverter VAR [var]', '#a5b9ff'), (12, 'Capacitor VAR [var]', '#4ee1bd'), (13, 'Capacitor line [A]', '#e6ae54'), (14, 'Flux [Wb turn]', '#a5b9ff'), (15, 'Cap energy [J]', '#4ee1bd'), (16, 'Bus frequency [Hz]', '#e6ae54'), (17, 'DC voltage [V]', '#68bbf3'), (18, 'DC brake heat [W]', '#ff7649'), (19, 'DC energy [J]', '#68bbf3'), (20, 'Rectifier input [W]', '#ffc36a'), (21, 'Chopper duty [0–1]', '#ffc36a'), (22, 'Exciter DC [W]', '#68bbf3'), (23, 'Exciter loss [W]', '#e0cc87'), (24, 'Battery input [W]', '#83d4be'), (25, 'Boost output [W]', '#60e0c1'), (26, 'Boost loss [W]', '#83d4be')]:
            top = history_y+32+(index-1)*83
            left, right, bottom = 175, width-22, top+63
            c.create_line(left,top,left,bottom,right,bottom,fill="#526075")
            values = [row[index] for row in self.history]
            low, high = min([0]+values), max([0]+values)
            if high-low < 1e-8:
                high = low+1
            label(22,top,f"{title}\n{low:.2f} … {high:.2f}",color=color,size=9)
            if len(values)>1:
                start = max(0, self.history[-1][0]-75)
                end = max(start+0.05, self.history[-1][0])
                points = []
                for row in self.history:
                    points.extend((left+(row[0]-start)/(end-start)*(right-left), bottom-(row[index]-low)/(high-low)*(bottom-top)))
                c.create_line(*points, fill=color, width=2)
                if index == 26:
                    label(left, bottom+2, f"{start:.2f} s", color="#93a3ba", size=8)
                    label(right, bottom+2, f"{end:.2f} s", color="#93a3ba", size=8, anchor="ne")
        c.configure(scrollregion=(0, 0, width, history_y+2240))

    def draw_crane(self, label):
        c, s, p = self.canvas, self.model.state, self.model.parameters
        # The static machinery is a generated technical illustration informed
        # by Liftra's LT1200 arrangement. Only simulated parts are drawn live.
        scene_x, scene_y = 18, 80
        c.create_rectangle(scene_x-1, scene_y-1, 610, 425, fill="#172b42", outline="#314862")
        c.create_image(scene_x, scene_y, image=self.crane_background, anchor="nw")
        tip_x, tip_y, ground = 394, 121, 410
        phase = s.angle % (2*math.pi)
        c.create_oval(tip_x-12, tip_y-12, tip_x+12, tip_y+12, fill="#13283a", outline="#5de0c1", width=3)
        c.create_line(tip_x, tip_y, tip_x+10*math.cos(phase), tip_y+10*math.sin(phase), fill="#5de0c1", width=3)
        fraction = min(1, max(0, s.position/p.crane_height))
        load_top = 160 + 210*fraction
        c.create_line(tip_x, tip_y+12, tip_x, load_top-18, fill="#edf5f7", width=3)
        c.create_oval(tip_x-8, load_top-20, tip_x+8, load_top-4, outline="#ffd46c", width=3)
        c.create_line(tip_x, load_top-4, tip_x-20, load_top+5, tip_x+20, load_top+5, tip_x, load_top-4, fill="#d8e5ea", width=2)
        c.create_rectangle(tip_x-34, load_top+5, tip_x+34, load_top+43, fill="#d78c3f", outline="#ffd58a", width=3)
        c.create_line(tip_x-19, load_top+5, tip_x-19, load_top+43, fill="#713e29", width=5)
        c.create_line(tip_x+19, load_top+5, tip_x+19, load_top+43, fill="#713e29", width=5)
        label(tip_x, load_top+24, f"{p.mass:g} kg", color="#fff2ce", anchor="center", size=9)
        c.create_line(590, 160, 590, ground, fill="#7d99b1", arrow="both", width=2)
        label(583, 285, f"{p.crane_height:g} m", color="#aac4d8", anchor="e", size=9)
        label(28, 407, "SELF-HOISTING CRANE · LIVE LOAD", color="#c4d8e6", size=9, anchor="sw")


def run():
    root = tk.Tk()
    Application(root)
    root.mainloop()
