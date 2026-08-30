"""Claude Code CLI and IDE process/session observer."""

from __future__ import annotations

import os
import re
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


class ClaudeProvider(AgentProvider):
    id, name = "claude", "Claude"
    _ACTIVE_FILE_SECONDS = 12

    def __init__(self, executable: str | None = None, claude_home: Path | None = None) -> None:
        self.executable = executable or find_executable(("claude",), (Path.home() / ".claude/local/claude",))
        self.claude_home = claude_home or Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
        self.version = binary_version(self.executable)

    def _processes(self) -> list[dict]:
        result = []
        for process in process_snapshot():
            executable = process["executable"]
            argv_name = Path(process["argv"][0]).name.lower()
            is_claude = executable in {"claude", "claude-code"} or argv_name in {"claude", "claude-code"}
            if not is_claude:
                is_claude = process_is_runtime(process, ("@anthropic-ai/claude-code", "/claude-code/"))
            if not is_claude:
                continue
            process["vscode"] = bool(
                {"VSCODE_PID", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT"}
                & process["environment_keys"]
            ) or "--ide" in process["argv"]
            result.append(process)
        return result

    def detect(self) -> bool:
        return bool(self.executable and Path(self.executable).exists()) or bool(self._processes())

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities({"status": True, "sessions": True, "workspace": True, "model": True})

    def _session_file(self, workspace: str | None, pid: int | None = None) -> Path | None:
        if pid is not None:
            open_sessions = [path for path in open_files(pid, ".jsonl") if "claude" in str(path).lower()]
            if open_sessions:
                return max(open_sessions, key=lambda path: path.stat().st_mtime)
        try:
            candidates = sorted(
                (self.claude_home / "projects").glob("**/*.jsonl"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )[:100]
        except OSError:
            return None
        # Claude filenames encode a project path, but process cwd is the
        # authoritative workspace and is intentionally not reverse-decoded.
        del workspace
        return candidates[0] if candidates else None

    def _event_state(self, path: Path | None) -> str | None:
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
            if re.search(r'"type"\s*:\s*"last-prompt"', line) or re.search(r'"type"\s*:\s*"user"', line):
                state = "working"
            elif re.search(r'"type"\s*:\s*"assistant"', line):
                stop_reason = re.search(r'"stop_reason"\s*:\s*"([^"]+)"', line)
                state = "idle" if stop_reason and stop_reason.group(1) == "end_turn" else "working"
        return state

    def get_sessions(self) -> list[AgentSession]:
        sessions = []
        for process in self._processes():
            path = self._session_file(process.get("cwd"), process["pid"])
            event_state = self._event_state(path)
            recent = is_recent(path, self._ACTIVE_FILE_SECONDS)
            status = AgentStatus.WORKING if event_state == "working" or (event_state is None and recent) else AgentStatus.IDLE
            source = SessionSource.VSCODE if process["vscode"] else SessionSource.CLI
            session_id = path.stem if path else f"claude-{process['pid']}"
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
                        "processKind": "vscode-ide" if process["vscode"] else "cli",
                        "statusEvidence": "session-event" if event_state else ("recent-session-file" if recent else "live-process"),
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
