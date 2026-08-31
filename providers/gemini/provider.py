"""Gemini CLI and Gemini Code Assist process/session observer."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from providers.google_process import process_snapshot, workspace_name
from vox_sentry.models import AgentSession, AgentStatus, ProviderCapabilities, SessionSource
from vox_sentry.provider import AgentProvider


class GeminiProvider(AgentProvider):
    id, name = "gemini", "Gemini"
    _ACTIVE_FILE_SECONDS = 12

    def __init__(self, executable: str | None = None, gemini_home: Path | None = None) -> None:
        self.executable = executable or self._find_executable()
        self.gemini_home = gemini_home or Path(
            os.environ.get("GEMINI_HOME", Path.home() / ".gemini")
        )
        self.version = self._version_from_binary()

    def _find_executable(self) -> str | None:
        executable = shutil.which("gemini")
        if executable:
            return executable
        # systemd user services do not necessarily load an interactive shell's
        # nvm PATH. Cover the normal per-user npm installation locations.
        candidates = [Path.home() / ".local/bin/gemini", Path.home() / ".npm-global/bin/gemini"]
        candidates.extend(Path.home().glob(".nvm/versions/node/*/bin/gemini"))
        return next((str(path) for path in sorted(candidates, reverse=True) if path.is_file()), None)

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

    def _processes(self) -> list[dict]:
        result = []
        for process in process_snapshot():
            executable = process["executable"]
            argv = process["argv"]
            command = process["command"]
            # The npm launcher can be a node process, so inspect argv as well as
            # /proc/<pid>/exe. Do not match arbitrary shells containing "gemini".
            is_gemini = executable in {"gemini", "gemini-cli"} or Path(argv[0]).name in {
                "gemini",
                "gemini-cli",
            }
            runtime = executable in {"node", "nodejs", "bun", "deno"} or Path(argv[0]).name in {
                "node",
                "nodejs",
                "bun",
                "deno",
            }
            if not is_gemini and not (
                runtime and any(marker in command for marker in ("@google/gemini-cli", "/gemini-cli/"))
            ):
                continue
            is_vscode = bool(
                {"VSCODE_PID", "GEMINI_CLI_SURFACE"} & process["environment_keys"]
            ) or any(marker in command for marker in ("a2a", "acp", "vscode"))
            result.append({**process, "vscode": is_vscode})
        return result

    def detect(self) -> bool:
        return bool(self.executable and Path(self.executable).exists()) or bool(self._processes())

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities({"status": True, "sessions": True, "workspace": True, "model": True})

    def _session_files(self) -> list[Path]:
        try:
            return sorted(
                (self.gemini_home / "tmp").glob("**/chats/*.jsonl"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )[:100]
        except OSError:
            return []

    def _metadata(self, path: Path) -> dict:
        """Read only the small session header; message records are never parsed."""
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                header = json.loads(handle.readline())
            if header.get("kind") != "main":
                return {}
            return {
                "session_id": header.get("sessionId"),
                "started_at": header.get("startTime"),
                "updated_at": header.get("lastUpdated"),
                "project_hash": header.get("projectHash"),
            }
        except (OSError, json.JSONDecodeError, TypeError):
            return {}

    def _recent_session(self, process: dict) -> tuple[dict, Path | None]:
        # Gemini's session files contain a project hash rather than a portable
        # cwd in their header. Pick the newest live session, while keeping the
        # process itself as the authoritative source of workspace and liveness.
        for path in self._session_files():
            metadata = self._metadata(path)
            if metadata:
                return metadata, path
        return {}, None

    def _model(self, argv: list[str]) -> str | None:
        for index, argument in enumerate(argv):
            if argument in {"--model", "-m"} and index + 1 < len(argv):
                return argv[index + 1]
            if argument.startswith("--model="):
                return argument.split("=", 1)[1]
        return None

    def _is_recent(self, path: Path | None) -> bool:
        if path is None:
            return False
        try:
            return time.time() - path.stat().st_mtime <= self._ACTIVE_FILE_SECONDS
        except OSError:
            return False

    def get_sessions(self) -> list[AgentSession]:
        sessions = []
        for process in self._processes():
            metadata, path = self._recent_session(process)
            status = AgentStatus.WORKING if self._is_recent(path) else AgentStatus.IDLE
            source = SessionSource.VSCODE if process["vscode"] else SessionSource.CLI
            session_id = metadata.get("session_id") or f"gemini-{process['pid']}"
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
                    self._model(process["argv"]),
                    metadata.get("started_at"),
                    metadata.get("updated_at") or datetime.now(timezone.utc).isoformat(),
                    metadata={
                        "observation": "process-and-session-metadata",
                        "processKind": "vscode-a2a" if process["vscode"] else "cli",
                        "statusEvidence": "recent-session-file" if self._is_recent(path) else "live-process",
                        "sessionFile": str(path) if path else None,
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
