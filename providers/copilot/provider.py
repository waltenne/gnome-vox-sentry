"""GitHub Copilot CLI and VS Code process/session observer."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from providers.google_process import open_files
from providers.terminal import (
    binary_version,
    find_executable,
    is_recent,
    model_from_argv,
    process_is_runtime,
    process_snapshot,
    workspace_name,
)
from vox_sentry.models import AgentSession, AgentStatus, ProviderCapabilities, SessionSource
from vox_sentry.provider import AgentProvider


class CopilotProvider(AgentProvider):
    id, name = "copilot", "Copilot"
    _ACTIVE_FILE_SECONDS = 12

    def __init__(self, executable: str | None = None, copilot_home: Path | None = None) -> None:
        self.executable = executable or find_executable(
            ("copilot", "github-copilot"),
            (
                Path.home()
                / ".config/Code/User/globalStorage/github.copilot-chat/copilotCli/copilot",
            ),
        )
        self.copilot_home = copilot_home or Path(os.environ.get("COPILOT_HOME", Path.home() / ".copilot"))
        # The VS Code shim asks whether to install the standalone CLI when
        # called with --version; never invoke that prompt from the daemon.
        embedded = self.executable and "globalstorage" in self.executable.lower()
        self.version = None if embedded else binary_version(self.executable)

    def _processes(self) -> list[dict]:
        result = []
        for process in process_snapshot():
            executable = process["executable"]
            argv_name = Path(process["argv"][0]).name.lower()
            is_copilot = executable in {"copilot", "github-copilot", "copilot-cli"} or argv_name in {
                "copilot",
                "github-copilot",
                "copilot-cli",
            }
            if not is_copilot:
                is_copilot = process_is_runtime(
                    process,
                    ("@github/copilot", "copilot-cli", "github-copilot", "copilotcli", "copilotclishim"),
                )
            if not is_copilot:
                continue
            process["vscode"] = bool({"VSCODE_PID", "COPILOT_AGENT_MODE"} & process["environment_keys"])
            result.append(process)
        return result

    def detect(self) -> bool:
        return bool(self.executable and Path(self.executable).exists()) or bool(self._processes())

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities({"status": True, "sessions": True, "workspace": True, "model": True})

    def _session_file(self, pid: int | None = None) -> Path | None:
        if pid is not None:
            open_sessions = [path for path in open_files(pid) if "copilot" in str(path).lower() and path.is_file()]
            if open_sessions:
                return max(open_sessions, key=lambda path: path.stat().st_mtime)
        try:
            candidates = sorted(
                self.copilot_home.glob("**/*"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return None
        return next(
            (
                path
                for path in candidates[:100]
                if path.is_file() and ("session" in path.name.lower() or path.suffix == ".jsonl")
            ),
            None,
        )

    def get_sessions(self) -> list[AgentSession]:
        sessions = []
        for process in self._processes():
            path = self._session_file(process["pid"])
            recent = is_recent(path, self._ACTIVE_FILE_SECONDS)
            explicit_run = any(argument in {"-p", "--prompt", "run"} for argument in process["argv"])
            status = AgentStatus.WORKING if recent or explicit_run else AgentStatus.IDLE
            source = SessionSource.VSCODE if process["vscode"] else SessionSource.CLI
            session_id = path.stem if path else f"copilot-{process['pid']}"
            if any(session.id == session_id for session in sessions):
                session_id = f"{session_id}-{process['pid']}"
            workspace = process.get("cwd")
            sessions.append(
                AgentSession(
                    session_id,
                    self.id,
                    source,
                    status,
                    process["pid"],
                    workspace,
                    workspace_name(workspace),
                    model_from_argv(process["argv"]),
                    None,
                    datetime.now(timezone.utc).isoformat(),
                    metadata={
                        "observation": "process-and-session-file",
                        "processKind": "vscode" if process["vscode"] else "cli",
                        "statusEvidence": "recent-session-or-run-flag" if recent or explicit_run else "live-process",
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
