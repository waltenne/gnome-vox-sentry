"""OpenCode CLI/TUI and local server observer."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from providers.terminal import (
    binary_version,
    find_executable,
    model_from_argv,
    process_is_runtime,
    process_snapshot,
    workspace_name,
)
from vox_sentry.models import AgentSession, AgentStatus, ProviderCapabilities, SessionSource
from vox_sentry.provider import AgentProvider


class OpenCodeProvider(AgentProvider):
    id, name = "opencode", "OpenCode"
    _ACTIVE_SECONDS = 12

    def __init__(self, executable: str | None = None, data_dir: Path | None = None) -> None:
        self.executable = executable or find_executable(("opencode", "opencode2"), (Path.home() / ".opencode/bin/opencode",))
        self.data_dir = data_dir or Path(os.environ.get("OPENCODE_DATA_DIR", Path.home() / ".local/share/opencode"))
        self.version = binary_version(self.executable)

    def _processes(self) -> list[dict]:
        result = []
        for process in process_snapshot():
            executable = process["executable"]
            argv_name = Path(process["argv"][0]).name.lower()
            is_opencode = executable in {"opencode", "opencode2"} or argv_name in {"opencode", "opencode2"}
            if not is_opencode:
                is_opencode = process_is_runtime(process, ("@opencode-ai", "/opencode/"))
            if not is_opencode:
                continue
            process["vscode"] = bool({"VSCODE_PID", "OPENCODE_CLIENT"} & process["environment_keys"])
            result.append(process)
        return result

    def detect(self) -> bool:
        return bool(self.executable and Path(self.executable).exists()) or bool(self._processes())

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities({"status": True, "sessions": True, "workspace": True, "model": True})

    def _database(self) -> Path:
        return self.data_dir / "opencode.db"

    def _latest_session(self, workspace: str | None) -> dict:
        database = self._database()
        if not database.exists():
            return {}
        try:
            with sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=0.2) as connection:
                row = connection.execute(
                    "SELECT id, directory, time_created, time_updated, model "
                    "FROM session WHERE directory = ? ORDER BY time_updated DESC LIMIT 1",
                    (workspace or "",),
                ).fetchone()
            if not row and workspace is None:
                row = connection.execute(
                    "SELECT id, directory, time_created, time_updated, model "
                    "FROM session ORDER BY time_updated DESC LIMIT 1"
                ).fetchone()
            if not row:
                return {}
            return {"id": row[0], "directory": row[1], "created": row[2], "updated": row[3], "model": row[4]}
        except (OSError, sqlite3.Error):
            return {}

    def _workspace(self, process: dict) -> str | None:
        if process.get("cwd"):
            return process["cwd"]
        for index, argument in enumerate(process["argv"]):
            if argument == "--cwd" and index + 1 < len(process["argv"]):
                return process["argv"][index + 1]
            if argument.startswith("--cwd="):
                return argument.split("=", 1)[1]
        return None

    def get_sessions(self) -> list[AgentSession]:
        sessions = []
        for process in self._processes():
            workspace = self._workspace(process)
            metadata = self._latest_session(workspace)
            updated = metadata.get("updated")
            recent = bool(updated and (datetime.now(timezone.utc).timestamp() * 1000 - updated <= self._ACTIVE_SECONDS * 1000))
            process_command = process["command"]
            status = AgentStatus.WORKING if recent or " run " in f" {process_command} " else AgentStatus.IDLE
            source = SessionSource.VSCODE if process["vscode"] else SessionSource.CLI
            session_id = metadata.get("id") or f"opencode-{process['pid']}"
            if any(session.id == session_id for session in sessions):
                session_id = f"{session_id}-{process['pid']}"
            model = metadata.get("model") or model_from_argv(process["argv"])
            sessions.append(
                AgentSession(
                    session_id,
                    self.id,
                    source,
                    status,
                    process["pid"],
                    workspace,
                    workspace_name(workspace),
                    model,
                    datetime.fromtimestamp(metadata["created"] / 1000, timezone.utc).isoformat() if metadata.get("created") else None,
                    datetime.fromtimestamp(updated / 1000, timezone.utc).isoformat() if updated else datetime.now(timezone.utc).isoformat(),
                    metadata={
                        "observation": "process-and-local-session-database",
                        "processKind": "vscode" if process["vscode"] else "cli-or-server",
                        "statusEvidence": "recent-session-database" if recent else "live-process",
                    },
                )
            )
        return sessions

    def get_status(self, sessions: list[AgentSession] | None = None) -> AgentStatus:
        sessions = self.get_sessions() if sessions is None else sessions
        if not self.detect() or not sessions:
            return AgentStatus.OFFLINE
        if any(session.status == AgentStatus.WORKING for session in sessions):
            return AgentStatus.WORKING
        return AgentStatus.IDLE
