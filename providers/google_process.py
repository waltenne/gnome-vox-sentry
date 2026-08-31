"""Small, privacy-preserving helpers shared by Google agent providers."""

from __future__ import annotations

import os
import time
from pathlib import Path

_PROCESS_CACHE_TTL = 1.0
_process_cache: tuple[float, list[dict]] | None = None


def proc_read(pid: int, name: str) -> str | None:
    try:
        return Path(f"/proc/{pid}/{name}").read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, PermissionError, OSError):
        return None


def process_snapshot(*, force: bool = False) -> list[dict]:
    """Return process metadata without collecting command output or file contents."""
    global _process_cache
    now = time.monotonic()
    if not force and _process_cache is not None and now - _process_cache[0] < _PROCESS_CACHE_TTL:
        # Providers annotate their own copies (for example with `vscode`).
        # Keep the cached base snapshot isolated from those annotations.
        return [dict(process) for process in _process_cache[1]]

    result = []
    try:
        entries = Path("/proc").iterdir()
    except OSError:
        return result
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        raw = proc_read(pid, "cmdline")
        if not raw:
            continue
        argv = [part for part in raw.split("\0") if part]
        if not argv:
            continue
        try:
            executable = Path(os.readlink(f"/proc/{pid}/exe")).name
        except (FileNotFoundError, PermissionError, OSError):
            executable = Path(argv[0]).name
        try:
            cwd = os.readlink(f"/proc/{pid}/cwd")
        except (FileNotFoundError, PermissionError, OSError):
            cwd = None
        environment = proc_read(pid, "environ") or ""
        environment_keys = set()
        environment_values = {}
        for item in environment.split("\0"):
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            environment_keys.add(key)
            if key == "CODEX_INTERNAL_ORIGINATOR_OVERRIDE":
                environment_values[key] = value
        result.append(
            {
                "pid": pid,
                "ppid": _parent_pid(pid),
                "argv": argv,
                "command": " ".join(argv).lower(),
                "executable": executable.lower(),
                "cwd": cwd,
                "environment_keys": environment_keys,
                "environment_values": environment_values,
            }
        )
    _process_cache = (now, result)
    return result


def invalidate_process_snapshot() -> None:
    """Drop the shared process snapshot before a new daemon refresh cycle."""
    global _process_cache
    _process_cache = None


def _parent_pid(pid: int) -> int | None:
    status = proc_read(pid, "status")
    if not status:
        return None
    for line in status.splitlines():
        if line.startswith("PPid:"):
            try:
                return int(line.split()[1])
            except (IndexError, ValueError):
                return None
    return None


def descendants(processes: list[dict], pid: int) -> list[dict]:
    children = {item["pid"]: [] for item in processes}
    for item in processes:
        if item.get("ppid") in children:
            children[item["ppid"]].append(item)
    result, pending = [], list(children.get(pid, []))
    while pending:
        child = pending.pop()
        result.append(child)
        pending.extend(children.get(child["pid"], []))
    return result


def open_files(pid: int, suffix: str | None = None) -> list[Path]:
    result = []
    try:
        for fd in Path(f"/proc/{pid}/fd").iterdir():
            try:
                target = Path(os.readlink(fd))
            except OSError:
                continue
            if target.exists() and (suffix is None or str(target).endswith(suffix)):
                result.append(target)
    except OSError:
        pass
    return result


def workspace_name(workspace: str | None) -> str | None:
    return Path(workspace).name if workspace else None
