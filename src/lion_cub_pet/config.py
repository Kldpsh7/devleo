from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir, user_log_dir, user_runtime_dir


@dataclass(slots=True)
class PetConfig:
    schema_version: int = 2
    visible: bool = True
    paused: bool = False
    movement: str = "roam"
    anchor: str = "none"
    x: int | None = None
    y: int | None = None
    screen: int = 0
    speed: float = 115.0
    scale: float = 1.0
    stationary_scale: float = 0.85
    opacity: float = 1.0
    always_on_top: bool = True
    click_through: bool = False
    personality: str = "playful"
    mode: str = "normal"
    dialogues: bool = True
    dialogue_interval: float = 24.0
    advice: bool = True
    advice_min_interval: float = 240.0
    advice_max_interval: float = 480.0
    pomodoro_enabled: bool = False
    pomodoro_phase: str = "focus"
    pomodoro_focus_minutes: float = 25.0
    pomodoro_break_minutes: float = 5.0
    rubber_duck_enabled: bool = False
    rubber_duck_min_interval: float = 600.0
    rubber_duck_max_interval: float = 1200.0
    quiet_hours_enabled: bool = False
    quiet_schedule_enabled: bool = False
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"
    dialogue_pack: str | None = None
    treats: int = 0
    mood: int = 60
    interaction_streak: int = 0
    last_interaction_date: str | None = None
    bounds: str = "full-screen"
    idle_delay: float = 4.0
    run_chance: int = 35
    snap_distance: int = 48
    avoid_cursor: bool = False
    animation: str = "auto"
    laptop: str = "auto"
    autostart: bool = False


def config_dir() -> Path:
    return Path(user_config_dir("lion-cub-pet", appauthor=False))


def config_path() -> Path:
    return config_dir() / "config.json"


def log_path() -> Path:
    return Path(user_log_dir("lion-cub-pet", appauthor=False)) / "pet.log"


def runtime_dir() -> Path:
    try:
        base = Path(user_runtime_dir("lion-cub-pet", appauthor=False))
    except RuntimeError:
        base = config_dir() / "run"
    base.mkdir(parents=True, exist_ok=True)
    return base


def load_config() -> PetConfig:
    path = config_path()
    if not path.exists():
        return PetConfig()
    raw = json.loads(path.read_text(encoding="utf-8"))
    allowed = {field.name for field in fields(PetConfig)}
    config = PetConfig(**{key: value for key, value in raw.items() if key in allowed})
    config.schema_version = PetConfig().schema_version
    return config


def save_config(config: PetConfig) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def parse_value(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "on", "yes"}:
        return True
    if lowered in {"false", "off", "no"}:
        return False
    if lowered in {"none", "null"}:
        return None
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value


def set_value(config: PetConfig, key: str, value: Any) -> None:
    if not hasattr(config, key):
        raise KeyError(key)
    current = getattr(config, key)
    if current is not None and not isinstance(value, type(current)):
        if isinstance(current, float) and isinstance(value, int):
            value = float(value)
        else:
            raise ValueError(f"{key} requires {type(current).__name__}")
    setattr(config, key, value)
