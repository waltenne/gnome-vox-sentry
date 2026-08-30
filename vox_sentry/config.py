from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_DIR = "gnome-vox-sentry"


def _xdg(name: str, fallback: Path) -> Path:
    return Path(os.environ.get(name, fallback))


def config_dir() -> Path: return _xdg("XDG_CONFIG_HOME", Path.home() / ".config") / APP_DIR
def data_dir() -> Path: return _xdg("XDG_DATA_HOME", Path.home() / ".local/share") / APP_DIR
def cache_dir() -> Path: return _xdg("XDG_CACHE_HOME", Path.home() / ".cache") / APP_DIR
def config_path() -> Path: return config_dir() / "config.json"


DEFAULT_CONFIG: dict[str, Any] = {"providerMode": "auto", "providers": {"codex": {"enabled": True}}, "monitoring": {"refreshInterval": 2}, "notifications": {"enabled": True, "events": {"waiting": True, "completed": True, "error": True, "rateLimited": True}}}


def _merge(default: dict[str, Any], supplied: dict[str, Any]) -> dict[str, Any]:
    result = dict(default)
    for key, value in supplied.items():
        result[key] = _merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
    return result


def load_config(path: Path | None = None) -> dict[str, Any]:
    try:
        with (path or config_path()).open(encoding="utf-8") as handle:
            value = json.load(handle)
        return _merge(DEFAULT_CONFIG, value if isinstance(value, dict) else {})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return _merge(DEFAULT_CONFIG, {})


def save_config(config: dict[str, Any], path: Path | None = None) -> Path:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp.replace(path)
    return path
