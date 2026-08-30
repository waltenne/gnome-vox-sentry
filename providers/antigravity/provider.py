"""Antigravity IDE/CLI observer based on its local agent process tree."""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from providers.google_process import descendants, open_files, process_snapshot, workspace_name
from vox_sentry.models import AgentSession, AgentStatus, ProviderCapabilities, SessionSource
from vox_sentry.provider import AgentProvider


class AntigravityProvider(AgentProvider):
    id, name = "antigravity", "Antigravity"
    # A hub is a long-lived transport process.  Its log can remain open after
    # the chat has been closed, so old log entries must not keep a session
    # visible forever.
    _RECENT_ACTIVITY_SECONDS = 30

    def __init__(self, executable: str | None = None) -> None:
        # Current Linux builds expose the backend as agy; older launchers expose
        # antigravity. Detection also works when the binary is not on PATH but is
        # already running.
        self.executable = executable or shutil.which("agy") or shutil.which("antigravity")
        self.version = self._version_from_binary()

    def _version_from_binary(self) -> str | None:
        if not self.executable:
            return None
        try:
            result = subprocess.run(
                [self.executable, "--version"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            return result.stdout.strip() or None
        except (OSError, subprocess.TimeoutExpired):
            return None

    def _processes(self, processes: list[dict] | None = None) -> list[dict]:
        result = []
        for process in processes if processes is not None else process_snapshot():
            executable = process["executable"]
            argv_name = Path(process["argv"][0]).name.lower()
            if executable not in {"agy", "antigravity"} and argv_name not in {
                "agy",
                "antigravity",
            }:
                continue
            process["vscode"] = bool(
                {"VSCODE_PID", "ANTIGRAVITY_VSCODE_HOST"} & process["environment_keys"]
            )
            result.append(process)
        return result

    def detect(self) -> bool:
        return bool(self.executable and Path(self.executable).exists()) or bool(self._processes())

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities({"status": True, "sessions": True, "workspace": True, "model": True})

    def _log_path(self, pid: int) -> Path | None:
        try:
            paths = [path for path in open_files(pid, ".log") if "antigravity" in str(path).lower()]
            return max(paths, key=lambda path: path.stat().st_mtime) if paths else None
        except OSError:
            return None

    def _log_state(self, pid: int) -> str | None:
        path = self._log_path(pid)
        if path is None:
            return None
        try:
            with path.open("rb") as handle:
                handle.seek(0, 2)
                handle.seek(max(0, handle.tell() - 131072))
                tail = handle.read().decode("utf-8", "replace")
        except OSError:
            return None
        state = None
        for line in tail.splitlines():
            if any(
                marker in line
                for marker in (
                    "Streaming conversation",
                    "Starting conversation update stream",
                    "Forwarding user message",
                    "Sending user message",
                    "streamGenerateContent",
                )
            ):
                state = "working"
            elif any(marker in line for marker in ("Full redraw completed", "conversation completed")):
                state = "idle"
        return state

    def _recent_log_state(self, pid: int) -> str | None:
        path = self._log_path(pid)
        if path is None:
            return None
        try:
            if time.time() - path.stat().st_mtime > self._RECENT_ACTIVITY_SECONDS:
                return None
        except OSError:
            return None
        return self._log_state(pid)

    def _conversation_db(self, process: dict) -> Path | None:
        root = Path.home() / (".gemini/antigravity-cli" if "--hub" not in process["argv"] else ".gemini/antigravity")
        try:
            databases = sorted((root / "conversations").glob("*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
        except OSError:
            return None
        return databases[0] if databases else None

    def _conversation_state(self, process: dict) -> str | None:
        database = self._conversation_db(process)
        if database is None:
            return None
        try:
            with sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=0.2) as connection:
                row = connection.execute("SELECT status FROM steps ORDER BY idx DESC LIMIT 1").fetchone()
            if not row:
                return None
            # Antigravity marks completed steps with status 3. Other statuses
            # mean the conversation still has work in progress.
            return "idle" if row[0] == 3 else "working"
        except (OSError, sqlite3.Error):
            return None

    def _workspace(self, process: dict) -> str | None:
        if process.get("cwd"):
            return process["cwd"]
        for argument in process["argv"]:
            if argument.startswith("--add-dir="):
                return argument.split("=", 1)[1]
        return None

    def _is_working(self, process: dict, all_processes: list[dict]) -> bool:
        # The hub stays alive while Antigravity is idle. Agent workers are
        # represented by descendants of the hub during an active task.
        if "--hub" not in process["argv"]:
            conversation_state = self._conversation_state(process)
            if conversation_state:
                return conversation_state == "working"
            log_state = self._log_state(process["pid"])
            if log_state:
                return log_state == "working"
            return any(
                marker in process["command"]
                for marker in ("--agent", "--task", "trajectory", " agent")
            )
        if self._active_worker(process, all_processes):
            return True
        return self._recent_log_state(process["pid"]) == "working"

    def _active_worker(self, process: dict, all_processes: list[dict]) -> bool:
        """Whether a hub has a live child that represents a real task."""
        for child in descendants(all_processes, process["pid"]):
            command = child["command"]
            is_agent_process = child.get("executable") in {"agy", "antigravity"} and "--hub" not in child["argv"]
            if is_agent_process or any(
                marker in command for marker in ("--agent", "--task", "trajectory")
            ):
                return True
        return False

    def _has_live_session(self, process: dict, all_processes: list[dict]) -> bool:
        """Exclude persistent hubs when no chat, CLI, or task is active."""
        if "--hub" not in process["argv"]:
            return True
        return self._active_worker(process, all_processes) or self._recent_log_state(process["pid"]) is not None

    def _model(self, argv: list[str]) -> str | None:
        for index, argument in enumerate(argv):
            if argument in {"--model", "-m"} and index + 1 < len(argv):
                return argv[index + 1]
            if argument.startswith("--model="):
                return argument.split("=", 1)[1]
        return None

    def get_sessions(self) -> list[AgentSession]:
        processes = process_snapshot()
        antigravity_processes = self._processes(processes)
        antigravity_pids = {process["pid"] for process in antigravity_processes}
        # A worker belongs to the hub session. Exposing only roots prevents one
        # task from appearing as several unrelated sessions in the panel.
        antigravity_processes = [
            process
            for process in antigravity_processes
            if process.get("ppid") not in antigravity_pids
        ]
        sessions = []
        for process in antigravity_processes:
            if not self._has_live_session(process, processes):
                continue
            source = SessionSource.VSCODE if process["vscode"] else SessionSource.DESKTOP
            status = AgentStatus.WORKING if self._is_working(process, processes) else AgentStatus.IDLE
            workspace = self._workspace(process)
            conversation_db = self._conversation_db(process)
            session_id = conversation_db.stem if conversation_db else f"antigravity-{process['pid']}"
            if any(session.id == session_id for session in sessions):
                session_id = f"{session_id}-{process['pid']}"
            sessions.append(
                AgentSession(
                    session_id,
                    self.id,
                    source,
                    status,
                    process["pid"],
                    workspace,
                    workspace_name(workspace),
                    self._model(process["argv"]),
                    None,
                    datetime.now(timezone.utc).isoformat(),
                    metadata={
                        "observation": "process-tree",
                        "processKind": "vscode-hub" if process["vscode"] else "hub-or-cli",
                        "statusEvidence": "conversation-log-or-database" if status == AgentStatus.WORKING else "live-process",
                        "conversationId": conversation_db.stem if conversation_db else None,
                    },
                )
            )
        return sessions

    def get_status(self) -> AgentStatus:
        sessions = self.get_sessions()
        if not self.detect() or not sessions:
            return AgentStatus.OFFLINE
        if any(session.status == AgentStatus.WORKING for session in sessions):
            return AgentStatus.WORKING
        return AgentStatus.IDLE
