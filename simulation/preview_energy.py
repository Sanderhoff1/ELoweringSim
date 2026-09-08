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
        texts=[item for item in items if item['kind']=='text' and item['text'].strip()]
        for index,a in enumerate(texts):
            for b in texts[index+1:]:
                x,y,X,Y=a['bbox'];u,v,U,V=b['bbox']
                assert not (min(X,U)>max(x,u)+1 and min(Y,V)>max(y,v)+1),(a['text'],b['text'])
        # Repeated paused draws must preserve all particle and rotor positions.
        frozen=[(canvas.type(i),canvas.coords(i)) for i in canvas.find_all()]
        app.draw()
        assert frozen==[(canvas.type(i),canvas.coords(i)) for i in canvas.find_all()]

        Path('docs/energy-canvas.json').write_text(json.dumps(data),encoding='utf-8')
        from .render_canvas import render
        render(target)
        bounds=canvas.bbox('all')
        assert bounds[0]>=0 and bounds[1]>=0 and bounds[2]<=data['width'] and bounds[3]<=data['height'],bounds
        print(target, data['width'],data['height'],bounds)
    dump('energy-preview.png')
    app.model.excitation_mode='capacitor';app.model.start_mode='precharged'
    from dataclasses import replace
    app.model.parameters=replace(app.model.parameters,precharge_voltage=200,initial_shaft_rpm=1600)
    app.model.startup_enabled=False;app.model.brake_released=True
    app.model.reset()
    for _ in range(1500):app.model.step()
    app.draw();root.update()
    dump('docs/capacitor-preview.png')
    app.model.parameters=replace(app.model.parameters,initial_shaft_rpm=0,initial_flux=.005)
    app.model.startup_enabled=True
    app.model.start_mode='residual';app.model.inverter_enabled=False
    app.model.reset();app.draw();root.update()
    dump('docs/residual-field-preview.png')
    app.model.start_mode='external_supply';app.model.inverter_enabled=True
    app.model.reset()
    for _ in range(100):app.model.step()
    app.draw();root.update()
    dump('docs/capacitor-startup-preview.png')
    root.destroy()


if __name__=='__main__':main()
