"""Render actual Tk canvas geometry at 1280 x 850, even without a desktop."""
import json
import subprocess
import tkinter as tk
from pathlib import Path
from .ui import Application


def main():
    root=tk.Tk()
    app=Application(root)
    root.geometry('1280x850+0+0')
    app.playing=False
    root.update()
    for _ in range(1500):app.model.step()
    root.update()
    app.draw()
    root.update()
    canvas=app.flow_canvas
    def dump(target):
        items=[]
        for ident in canvas.find_all():
            kind=canvas.type(ident)
            options={key:canvas.itemcget(ident,key) for key in ('fill',)}
            for key in ('outline','width','font','text','arrow','dash'):
                try:options[key]=canvas.itemcget(ident,key)
                except tk.TclError:pass
            items.append(dict(kind=kind,coords=canvas.coords(ident),bbox=canvas.bbox(ident),**options))
        data=dict(width=canvas.winfo_width(),height=canvas.winfo_height(),items=items)
        Path('docs/energy-canvas.json').write_text(json.dumps(data),encoding='utf-8')
        subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File','simulation/render_canvas.ps1','-OutputPath',target],check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        bounds=canvas.bbox('all')
        assert bounds[0]>=0 and bounds[1]>=0 and bounds[2]<=data['width'] and bounds[3]<=data['height'],bounds
        print(target, data['width'],data['height'],bounds)
    dump('energy-preview.png')
    app.model.excitation_mode='capacitor';app.model.start_mode='precharged'
    from dataclasses import replace
    app.model.parameters=replace(app.model.parameters,precharge_voltage=200)
    app.model.reset()
    app.draw();root.update()
    dump('docs/capacitor-preview.png')
    root.destroy()


if __name__=='__main__':main()
