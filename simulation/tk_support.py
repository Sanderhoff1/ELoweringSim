"""Create Tk roots when a sandboxed Python cannot expose its Tcl scripts."""
import os
from pathlib import Path
import shutil
import sys
import tkinter as tk


def _local_library():
    return Path(__file__).resolve().parents[1]/'.python'/'tcl'


def _configure(root):
    os.environ['TCL_LIBRARY']=str(root/'tcl8.6')
    os.environ['TK_LIBRARY']=str(root/'tk8.6')


def _stage_runtime_library():
    target=_local_library()
    candidates=(Path(sys.base_prefix)/'tcl',Path(sys.executable).resolve().parent/'tcl')
    for source in candidates:
        if source.resolve()==target.resolve():
            if (target/'tcl8.6'/'init.tcl').is_file() and (target/'tk8.6'/'tk.tcl').is_file():
                return target
            continue
        if (source/'tcl8.6'/'init.tcl').is_file() and (source/'tk8.6'/'tk.tcl').is_file():
            target.mkdir(parents=True,exist_ok=True)
            shutil.copytree(source/'tcl8.6',target/'tcl8.6',dirs_exist_ok=True)
            shutil.copytree(source/'tk8.6',target/'tk8.6',dirs_exist_ok=True)
            return target
    raise RuntimeError('Python includes _tkinter but no matching Tcl/Tk script libraries were found')


def create_root():
    """Return a Tk root, staging matching runtime scripts only when required."""
    local=_local_library()
    if (local/'tcl8.6'/'init.tcl').is_file() and (local/'tk8.6'/'tk.tcl').is_file():
        _configure(local)
    try:
        return tk.Tk()
    except tk.TclError as error:
        if 'usable init.tcl' not in str(error):
            raise
        staged=_stage_runtime_library()
        _configure(staged)
        return tk.Tk()
