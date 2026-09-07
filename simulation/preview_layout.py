"""Capture the real application at the target desktop size."""
import ctypes
import subprocess
import tkinter as tk
from pathlib import Path
from .ui import Application


def main():
    ctypes.windll.user32.SetProcessDPIAware()
    root = tk.Tk()
    app = Application(root)
    root.geometry('1280x800+0+0')
    root.update()
    app.draw()
    root.update()
    c = app.flow_canvas
    bounds = c.bbox('all')
    assert bounds[0] >= 0 and bounds[1] >= 0, bounds
    assert bounds[2] <= c.winfo_width() and bounds[3] <= c.winfo_height(), bounds
    target = str(Path('layout-preview.png').resolve()).replace("'", "''")
    script = f"""+Add-Type -AssemblyName System.Drawing
$bitmap = New-Object System.Drawing.Bitmap(1280,800)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen({root.winfo_rootx()},{root.winfo_rooty()},0,0,$bitmap.Size)
$bitmap.Save('{target}',[System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
""".lstrip('+')
    subprocess.run(['powershell','-NoProfile','-Command',script],check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW)
    root.destroy()
    print('Rendered 1280x800; all diagram content fits:', bounds)


if __name__ == '__main__':
    main()
