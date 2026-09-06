"""Manual UI review: python -m simulation.preview_energy (writes preview PNG)."""
import subprocess
import ctypes
import tkinter as tk
from pathlib import Path
from .ui import Application


def main():
    ctypes.windll.user32.SetProcessDPIAware()
    root = tk.Tk()
    app = Application(root)
    assert app.model.external_exciter and app.model.state.omega==0
    assert app.model.electrical.dc_energy==0 and app.model.parameters.initial_flux==0
    for _ in range(1500):
        app.model.step()
        app.sample()
    assert app.model.release_time is not None
    assert app.model.readings()['rectifier_power']>500
    root.state('zoomed')
    root.update()
    app.draw()
    root.update()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    target = str(Path('energy-preview.png').resolve()).replace("'", "''")
    script = f"""
Add-Type -AssemblyName System.Drawing
$capture = New-Object System.Drawing.Bitmap({w}, {h})
$graphics = [System.Drawing.Graphics]::FromImage($capture)
$graphics.CopyFromScreen({x}, {y}, 0, 0, $capture.Size)
$capture.Save('{target}', [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$capture.Dispose()
"""
    subprocess.run(['powershell', '-NoProfile', '-Command', script],
                   check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    print('Saved', target)
    root.state('normal')
    for size in ('1280x850','1000x700','720x480'):
        root.geometry(size)
        root.update()
        app.draw()
        bounds = app.flow_canvas.bbox('all')
        region = tuple(float(x) for x in app.flow_canvas.cget('scrollregion').split())
        assert bounds[0] >= 0 and bounds[1] >= 0
        assert bounds[2] <= region[2] and bounds[3] <= region[3], (size,bounds,region)
        print('Content accessible:',size)
    app.view_tabs.select(1)
    root.update()
    app.draw()
    app.view_tabs.select(0)
    app.preset.set('24 V startup')
    app.load_demo()
    app.live_converter_sliders['boost_target_voltage'][0].set(550)
    app.apply_converter_setting('boost_target_voltage')
    assert app.model.parameters.boost_target_voltage==520  # Preserve separation from chopper.
    app.live_converter_sliders['boost_input_power_limit'][0].set(300)
    app.apply_converter_setting('boost_input_power_limit')
    assert app.model.parameters.boost_input_power_limit==300
    before_boost=(app.model.state.time,app.model.electrical.dc_voltage)
    app.boost_enabled.set(False)
    app.toggle_boost()
    assert not app.model.boost_enabled
    app.boost_enabled.set(True)
    app.toggle_boost()
    assert app.model.boost_enabled
    assert before_boost==(app.model.state.time,app.model.electrical.dc_voltage)
    app.preset.set('24 V startup')
    app.load_demo()
    assert app.model.electrical.dc_voltage==0 and app.model.state.omega==0
    assert not app.model.brake_released and not app.model.inverter_enabled
    assert app.model.boost_enabled
    app.preset.set('Exciter handover')
    app.start_example()
    app.playing = False
    app.toggle_exciter_from_diagram()
    assert not app.model.inverter_enabled
    assert app.model.parameters.mass == 300
    for _ in range(25):
        app.model.step()
        app.sample()
    before = (app.model.state.time,app.model.electrical.dc_voltage)
    app.resistance_slider.set(600)
    app.apply_resistance()
    assert app.model.parameters.dc_brake_resistance == 600
    assert before == (app.model.state.time,app.model.electrical.dc_voltage)
    app.live_converter_sliders['inverter_current_limit'][0].set(0.5)
    app.apply_converter_setting('inverter_current_limit')
    assert app.model.parameters.inverter_current_limit==0.5
    assert before == (app.model.state.time,app.model.electrical.dc_voltage)
    app.chopper_enabled.set(False)
    app.toggle_chopper()
    assert not app.model.chopper_enabled
    app.capacitors.set(False)
    app.connect_capacitors()
    assert app.capacitors.get()  # Unsupported passive/no-AC-storage case is rejected.
    app.view_tabs.select(1)
    root.update()
    app.draw()
    app.converter_mode.set('6 · Chopper + ideal exciter')
    app.change_power_stage()
    assert app.model.chopper_active and not app.model.dc_exciter
    app.converter_mode.set('5 · Direct resistance')
    app.change_power_stage()
    app.rectifier.set(False)
    app.connect_rectifier()
    assert not app.model.rectifier_enabled
    app.dynamic_mode.set(False)
    app.change_model()
    app.draw()
    print('Startup, live boost/resistor controls, threshold guard, mode fallback and details tab OK')
    root.destroy()


if __name__ == '__main__':
    main()
