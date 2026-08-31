"""Common helpers for local terminal/IDE agent observers."""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from providers.google_process import process_snapshot, workspace_name


def find_executable(names: tuple[str, ...], extra: tuple[Path, ...] = ()) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    candidates = list(extra)
    for name in names:
        candidates.extend(
            [Path.home() / ".local/bin" / name, Path.home() / ".npm-global/bin" / name]
        )
        candidates.extend(Path.home().glob(f".nvm/versions/node/*/bin/{name}"))
    return next((str(path) for path in sorted(candidates, reverse=True) if path.is_file()), None)


def binary_version(executable: str | None) -> str | None:
    if not executable:
        return None
    try:
        result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, timeout=2, check=False
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def model_from_argv(argv: list[str]) -> str | None:
    for index, argument in enumerate(argv):
        if argument in {"--model", "-m"} and index + 1 < len(argv):
            return argv[index + 1]
        if argument.startswith("--model="):
            return argument.split("=", 1)[1]
    return None


def is_recent(path: Path | None, seconds: int) -> bool:
    if path is None:
        return False
    try:
        return time.time() - path.stat().st_mtime <= seconds
    except OSError:
        return False


def process_is_runtime(process: dict, markers: tuple[str, ...]) -> bool:
    executable = process["executable"]
    argv0 = Path(process["argv"][0]).name.lower()
    if executable not in {"node", "nodejs", "bun", "deno"} and argv0 not in {
        "node",
        "nodejs",
        "bun",
        "deno",
    }:
        return False
    return any(marker in process["command"] for marker in markers)


__all__ = [
    "binary_version",
    "find_executable",
    "is_recent",
    "model_from_argv",
    "process_is_runtime",
    "process_snapshot",
    "workspace_name",
]
