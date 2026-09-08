"""Repeatable 300 kg Energy Flow performance benchmark.

Run from the repository root with::

    python -m simulation.benchmark_energy_view
"""
from dataclasses import fields, is_dataclass
import math
import statistics
import sys
import time
import tkinter as tk

from .energy_view import EnergyView
from .external_model import ExternalLoweringModel, reviewed_parameters
from .ui import ReplayFrame, ReplayState, interpolate_telemetry


def deep_size(value, seen=None):
    seen = set() if seen is None else seen
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    size = sys.getsizeof(value)
    if isinstance(value, dict):
        return size+sum(deep_size(k, seen)+deep_size(v, seen) for k, v in value.items())
    if isinstance(value, (list, tuple, set, frozenset)):
        return size+sum(deep_size(v, seen) for v in value)
    if is_dataclass(value):
        return size+sum(deep_size(getattr(value, f.name), seen) for f in fields(value))
    return size


def summary(name, values):
    print(f'{name}: avg {statistics.mean(values)*1000:.3f} ms; '
          f'max {max(values)*1000:.3f} ms')


def main(samples=300):
    model = ExternalLoweringModel(reviewed_parameters(mass=300))
    model.brake_released = True
    physics = []
    for _ in range(samples):
        started = time.perf_counter()
        model.step()
        physics.append(time.perf_counter()-started)
    reading_times = []
    readings = None
    for _ in range(samples):
        started = time.perf_counter()
        readings = model.readings()
        reading_times.append(time.perf_counter()-started)
    readings['_time'] = model.state.time

    root = tk.Tk()
    root.withdraw()
    canvas = tk.Canvas(root, width=960, height=690)
    canvas.pack()
    root.update_idletasks()
    view = EnergyView(canvas, lambda: None)
    view.draw(model, readings, [], True)
    root.update_idletasks()
    render = []
    replay = []
    following = dict(readings)
    following['_time'] += .02
    following['position'] += following['velocity']*.02
    following['angle'] += following['omega']*.02
    for index in range(samples):
        visual_time = readings['_time']+index/60
        started = time.perf_counter()
        view.draw(model, readings, [], True, visual_time=visual_time,
                  update_text=index % 4 == 0)
        root.update_idletasks()
        render.append(time.perf_counter()-started)
        started = time.perf_counter()
        interpolated = interpolate_telemetry(readings, following, (index % 6)/6)
        view.draw(model, interpolated, [], True, visual_time=visual_time,
                  update_text=index % 4 == 0)
        root.update_idletasks()
        replay.append(time.perf_counter()-started)

    state = model.state
    frame = ReplayFrame(
        state.time, readings,
        ReplayState(state.time, state.position, state.angle, state.omega,
                    state.grounded, state.impact_speed, state.impact_energy),
        model.brake_released, model.motor_connected, model.inverter_enabled,
        model.capacitors_enabled)
    frame_bytes = deep_size(frame)
    summary('physics step', physics)
    summary('readings/diagnostics', reading_times)
    summary('persistent update/render', render)
    summary('interpolated replay frame', replay)
    print(f'raw render capacity: {1/statistics.mean(render):.1f} FPS')
    print(f'60 Hz scheduled playback headroom: '
          f'{100*(1-statistics.mean(replay)/(1/60)):.1f}%')
    scheduled_periods = []
    previous = [None]
    index = [0]
    target = [time.perf_counter()]

    def scheduled_frame():
        now = time.perf_counter()
        if previous[0] is not None:
            scheduled_periods.append(now-previous[0])
        previous[0] = now
        fraction = (index[0] % 6)/6
        interpolated = interpolate_telemetry(readings, following, fraction)
        view.draw(model, interpolated, [], True, visual_time=readings['_time']+index[0]/60,
                  update_text=index[0] % 4 == 0)
        index[0] += 1
        if index[0] >= 180:
            root.quit()
            return
        target[0] += 1/60
        root.after(max(0, math.ceil((target[0]-time.perf_counter())*1000)), scheduled_frame)

    root.after(0, scheduled_frame)
    root.mainloop()
    print(f'scheduled replay: {1/statistics.mean(scheduled_periods):.1f} FPS; '
          f'max frame period {max(scheduled_periods)*1000:.2f} ms')
    print(f'canvas items created once: {len(canvas.find_all())}')
    print(f'canvas item updates in final frame: {view.updates_last_frame}')
    print(f'one telemetry frame: {frame_bytes/1024:.1f} KiB; '
          f'10 s at 50 Hz: {frame_bytes*501/1024/1024:.1f} MiB approximate')
    root.destroy()


if __name__ == '__main__':
    main()
