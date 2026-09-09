"""Open, versioned persistence for lightweight pre-simulation replay frames."""
from __future__ import annotations

import csv
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from .parameters import Parameters


FORMAT_ID = "elowering-pre-simulation"
FORMAT_VERSION = 1


@dataclass(frozen=True)
class ReplayState:
    time: float
    position: float
    angle: float
    omega: float
    grounded: bool
    impact_speed: float
    impact_energy: float


@dataclass(frozen=True)
class ReplayFrame:
    """One lightweight playback sample; independent of the physics model."""
    t: float
    readings: dict
    state: ReplayState
    brake_released: bool
    motor_connected: bool
    inverter_enabled: bool
    capacitors_enabled: bool


@dataclass(frozen=True)
class LoadedReplay:
    frames: tuple[ReplayFrame, ...]
    metadata: dict
    csv_path: Path
    metadata_path: Path


_ALIASES = {
    "_time": ("telemetry_time_s", "s", 1.0),
    "position": ("load_position_m", "m", 1.0),
    "velocity": ("load_speed_m_min", "m/min", 60.0),
    "acceleration": ("load_acceleration_m_s2", "m/s^2", 1.0),
    "angle": ("rotor_angle_rad", "rad", 1.0),
    "omega": ("motor_speed_rad_s", "rad/s", 1.0),
    "rpm": ("motor_rpm", "RPM", 1.0),
    "synchronous_rpm": ("synchronous_speed_rpm", "RPM", 1.0),
    "line_voltage": ("ac_voltage_v_ll_rms", "V LL RMS", 1.0),
    "machine_line_current": ("motor_current_a_rms", "A RMS", 1.0),
    "machine_active_current": ("motor_active_current_a_rms", "A RMS", 1.0),
    "machine_reactive_current": ("motor_reactive_current_a_rms", "A RMS", 1.0),
    "electrical_export": ("generated_active_power_w", "W", 1.0),
    "inverter_reactive_supply": ("inverter_reactive_power_var", "var", 1.0),
    "bus_frequency": ("ac_frequency_hz", "Hz", 1.0),
    "stator_frequency_command": ("frequency_command_hz", "Hz", 1.0),
    "frequency_target": ("frequency_target_hz", "Hz", 1.0),
    "flux_magnitude": ("magnetic_flux_wb_turn", "Wb turn", 1.0),
    "flux_target": ("magnetic_flux_target_wb_turn", "Wb turn", 1.0),
    "maximum_flux": ("maximum_magnetic_flux_wb_turn", "Wb turn", 1.0),
    "dc_voltage": ("dc_link_voltage_v", "V DC", 1.0),
    "dc_brake_power": ("resistor_power_w", "W", 1.0),
    "rectifier_power": ("rectifier_dc_power_w", "W", 1.0),
    "motor_torque": ("motor_torque_nm", "N m", 1.0),
}


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return _json_value(value.value)
    if is_dataclass(value):
        return {item.name: _json_value(getattr(value, item.name))
                for item in fields(value)}
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def parameter_snapshot(parameters: Parameters) -> dict:
    """Snapshot every dataclass field and its engineering metadata."""
    snapshot = {}
    for item in fields(parameters):
        snapshot[item.name] = {
            "value": _json_value(getattr(parameters, item.name)),
            "unit": item.metadata.get("unit", ""),
            "meaning": item.metadata.get("meaning", ""),
            "status": item.metadata.get("status", ""),
            "minimum": _json_value(item.metadata.get("minimum")),
            "maximum": _json_value(item.metadata.get("maximum")),
        }
    return snapshot


def replay_parameters(snapshot: dict, current: Parameters) -> Parameters:
    """Build a separate display context without changing current parameters."""
    valid = {item.name for item in fields(current)}
    values = {name: details["value"] for name, details in snapshot.items()
              if name in valid and isinstance(details, dict) and "value" in details}
    return replace(current, **values)


def scalar_configuration(obj: Any, *, exclude=()) -> dict:
    """Capture public scalar configuration, including class-level switches."""
    excluded = set(exclude)
    result = {}
    for name in dir(obj):
        if name.startswith("_") or name in excluded:
            continue
        try:
            value = getattr(obj, name)
        except (AttributeError, ValueError):
            continue
        if value is None or isinstance(value, (str, bool, int, float, Enum)):
            result[name] = _json_value(value)
        elif is_dataclass(value):
            result[name] = _json_value(value)
    return result


def _flatten(value: dict, prefix=()):
    for key, item in value.items():
        path = prefix + (str(key),)
        if isinstance(item, dict):
            yield from _flatten(item, path)
        else:
            yield path, item


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return value or "value"


def _inferred_unit(name: str) -> tuple[str, str]:
    lower = name.lower()
    if "reactive" in lower or lower.endswith("_q") or "_q_" in lower:
        return "var", "var"
    if lower.endswith("_rpm") or lower == "rpm":
        return "rpm", "RPM"
    if "frequency" in lower:
        return "hz", "Hz"
    if "current" in lower:
        return "a", "A"
    if "voltage" in lower:
        return "v", "V"
    if "energy" in lower:
        return "j", "J"
    if any(word in lower for word in ("power", "loss", "heat", "storage_rate")):
        return "w", "W"
    if "torque" in lower:
        return "nm", "N m"
    if lower.endswith("elapsed") or lower.endswith("_time") or "delay_remaining" in lower:
        return "s", "s"
    return "", ""


def _reading_column(path: tuple[str, ...]) -> tuple[str, str, float]:
    if len(path) == 1 and path[0] in _ALIASES:
        return _ALIASES[path[0]]
    base = "__".join(_slug(part) for part in path)
    suffix, unit = _inferred_unit(path[-1])
    if suffix and not base.endswith("_" + suffix):
        base += "_" + suffix
    return base, unit, 1.0


def _value_type(values) -> str:
    present = [value for value in values if value is not _MISSING and value is not None]
    if not present:
        return "json"
    if all(isinstance(value, bool) for value in present):
        return "bool"
    if all(isinstance(value, int) and not isinstance(value, bool) for value in present):
        return "int"
    if all(isinstance(value, (int, float)) and not isinstance(value, bool)
           for value in present):
        return "float"
    if all(isinstance(value, str) for value in present):
        return "string"
    return "json"


_MISSING = object()


def _schema(frames: tuple[ReplayFrame, ...]) -> list[dict]:
    schema = [
        {"column": "time_s", "section": "frame", "path": ["t"], "type": "float", "unit": "s"},
        {"column": "replay_state_time_s", "section": "state", "path": ["time"], "type": "float", "unit": "s"},
        {"column": "replay_state_load_position_m", "section": "state", "path": ["position"], "type": "float", "unit": "m"},
        {"column": "replay_state_rotor_angle_rad", "section": "state", "path": ["angle"], "type": "float", "unit": "rad"},
        {"column": "replay_state_motor_speed_rad_s", "section": "state", "path": ["omega"], "type": "float", "unit": "rad/s"},
        {"column": "replay_state_grounded", "section": "state", "path": ["grounded"], "type": "bool", "unit": ""},
        {"column": "replay_state_impact_speed_m_s", "section": "state", "path": ["impact_speed"], "type": "float", "unit": "m/s"},
        {"column": "replay_state_impact_energy_j", "section": "state", "path": ["impact_energy"], "type": "float", "unit": "J"},
        {"column": "brake_released", "section": "frame", "path": ["brake_released"], "type": "bool", "unit": ""},
        {"column": "motor_connected", "section": "frame", "path": ["motor_connected"], "type": "bool", "unit": ""},
        {"column": "inverter_enabled", "section": "frame", "path": ["inverter_enabled"], "type": "bool", "unit": ""},
        {"column": "capacitors_enabled", "section": "frame", "path": ["capacitors_enabled"], "type": "bool", "unit": ""},
    ]
    flattened = [dict(_flatten(frame.readings)) for frame in frames]
    paths = sorted({path for values in flattened for path in values})
    used = {item["column"] for item in schema}
    for path in paths:
        column, unit, scale = _reading_column(path)
        candidate, index = column, 2
        while candidate in used:
            candidate = f"{column}_{index}"
            index += 1
        used.add(candidate)
        item = {
            "column": candidate,
            "section": "readings",
            "path": list(path),
            "type": _value_type(values.get(path, _MISSING) for values in flattened),
            "unit": unit,
        }
        if scale != 1.0:
            item["csv_scale"] = scale
        schema.append(item)
    return schema


def _source_value(frame: ReplayFrame, item: dict):
    section, path = item["section"], item["path"]
    if section == "frame":
        return getattr(frame, path[0])
    if section == "state":
        return getattr(frame.state, path[0])
    value = frame.readings
    for name in path:
        if not isinstance(value, dict) or name not in value:
            return _MISSING
        value = value[name]
    return value


def _encode(value, item):
    if value is _MISSING:
        return ""
    if value is None:
        return "null"
    scale = item.get("csv_scale", 1.0)
    if item["type"] == "bool":
        return "true" if value else "false"
    if item["type"] in ("int", "float"):
        return repr(value * scale)
    if item["type"] == "string":
        return value
    return json.dumps(_json_value(value), ensure_ascii=False, separators=(",", ":"))


def save_pre_simulation(path, frames, parameters_snapshot: dict,
                        run_configuration: dict, telemetry_interval_s: float) -> tuple[Path, Path, dict]:
    """Write a CSV dataset and adjacent JSON metadata file."""
    csv_path = Path(path)
    if csv_path.suffix.lower() == ".json":
        csv_path = csv_path.with_suffix(".csv")
    elif csv_path.suffix.lower() != ".csv":
        csv_path = csv_path.with_suffix(".csv")
    metadata_path = csv_path.with_suffix(".json")
    frames = tuple(frames)
    if not frames:
        raise ValueError("There are no replay frames to save.")
    schema = _schema(frames)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[item["column"] for item in schema])
        writer.writeheader()
        for frame in frames:
            writer.writerow({item["column"]: _encode(_source_value(frame, item), item)
                             for item in schema})
    digest = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    metadata = {
        "format": FORMAT_ID,
        "format_version": FORMAT_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "telemetry_file": csv_path.name,
        "telemetry_sha256": digest,
        "frame_count": len(frames),
        "duration_s": frames[-1].t,
        "telemetry_interval_s": telemetry_interval_s,
        "parameter_type": "simulation.parameters.Parameters",
        "parameters": _json_value(parameters_snapshot),
        "run_configuration": _json_value(run_configuration),
        "csv_schema": schema,
    }
    with metadata_path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(metadata, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    return csv_path, metadata_path, metadata


def _decode(value: str, item: dict):
    kind = item["type"]
    if kind == "string":
        return value
    if value == "":
        return _MISSING
    if kind == "bool":
        if value not in ("true", "false"):
            raise ValueError(f"Invalid boolean in {item['column']}: {value!r}")
        return value == "true"
    if kind == "int":
        return int(value)
    if kind == "float":
        result = float(value) / item.get("csv_scale", 1.0)
        if not math.isfinite(result):
            raise ValueError(f"Non-finite number in {item['column']}")
        return result
    return json.loads(value)


def _set_nested(target: dict, path: list[str], value):
    current = target
    for name in path[:-1]:
        current = current.setdefault(name, {})
    current[path[-1]] = value


def _pair_paths(path) -> tuple[Path, Path]:
    selected = Path(path)
    if selected.suffix.lower() == ".json":
        return selected.with_suffix(".csv"), selected
    if selected.suffix.lower() == ".csv":
        return selected, selected.with_suffix(".json")
    raise ValueError("Select the replay .csv or its adjacent .json metadata file.")


def load_pre_simulation(path) -> LoadedReplay:
    """Load replay frames without constructing or stepping a physics model."""
    default_csv, metadata_path = _pair_paths(path)
    with metadata_path.open("r", encoding="utf-8") as stream:
        metadata = json.load(stream)
    if metadata.get("format") != FORMAT_ID:
        raise ValueError("This is not an ELowering pre-simulation file.")
    version = metadata.get("format_version")
    if version != FORMAT_VERSION:
        raise ValueError(f"Unsupported replay format version {version!r}; expected {FORMAT_VERSION}.")
    csv_path = metadata_path.parent / metadata.get("telemetry_file", default_csv.name)
    if not csv_path.is_file():
        raise ValueError(f"Replay telemetry file is missing: {csv_path.name}")
    expected_digest = metadata.get("telemetry_sha256")
    if expected_digest and hashlib.sha256(csv_path.read_bytes()).hexdigest() != expected_digest:
        raise ValueError("Replay CSV checksum does not match its metadata file.")
    schema = metadata.get("csv_schema")
    if not isinstance(schema, list) or not schema:
        raise ValueError("Replay metadata does not contain a CSV schema.")
    frames_out = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = [item["column"] for item in schema]
        missing = [column for column in required if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("Replay CSV is missing columns: " + ", ".join(missing))
        for row in reader:
            frame_values, state_values, readings = {}, {}, {}
            for item in schema:
                value = _decode(row[item["column"]], item)
                if value is _MISSING:
                    continue
                if item["section"] == "frame":
                    frame_values[item["path"][0]] = value
                elif item["section"] == "state":
                    state_values[item["path"][0]] = value
                else:
                    _set_nested(readings, item["path"], value)
            state = ReplayState(**state_values)
            frames_out.append(ReplayFrame(
                t=frame_values["t"], readings=readings, state=state,
                brake_released=frame_values["brake_released"],
                motor_connected=frame_values["motor_connected"],
                inverter_enabled=frame_values["inverter_enabled"],
                capacitors_enabled=frame_values["capacitors_enabled"]))
    expected_count = metadata.get("frame_count")
    if expected_count != len(frames_out):
        raise ValueError(f"Replay frame count mismatch: metadata says {expected_count}, CSV has {len(frames_out)}.")
    if not frames_out:
        raise ValueError("Replay CSV contains no frames.")
    return LoadedReplay(tuple(frames_out), metadata, csv_path, metadata_path)
