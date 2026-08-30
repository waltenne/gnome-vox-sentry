"""Codex provider using conservative local observations.

The provider reads executable/process metadata, session metadata and event/item type envelopes.
It never reads rollout message content. Authenticated usage and limit summaries are requested
through a short-lived local app-server client and are kept separate from session observation.
"""

from __future__ import annotations

import json
import os
import selectors
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from vox_sentry.models import (
    AgentSession,
    AgentStatus,
    AgentUsage,
    ProviderCapabilities,
    SessionSource,
)
from vox_sentry.provider import AgentProvider


def _proc_read(pid: int, name: str) -> str | None:
    try:
        return Path(f"/proc/{pid}/{name}").read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, PermissionError, OSError):
        return None


class CodexProvider(AgentProvider):
    id, name = "codex", "Codex"

    def __init__(self, executable: str | None = None, codex_home: Path | None = None) -> None:
        self.executable = executable or shutil.which("codex")
        self.codex_home = codex_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        self.version = self._version_from_binary()
        self._account_cache: AgentUsage | None = None
        self._account_cache_at = 0.0

    def _version_from_binary(self) -> str | None:
        if not self.executable: return None
        try:
            result = subprocess.run([self.executable, "--version"], capture_output=True, text=True, timeout=2, check=False)
            return result.stdout.strip() or None
        except (OSError, subprocess.TimeoutExpired): return None

    def detect(self) -> bool:
        # The VS Code extension can bundle and launch its own Codex binary,
        # so PATH alone is not sufficient to identify an active installation.
        return bool(self.executable and Path(self.executable).exists()) or bool(self._processes())

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities({"status": True, "sessions": True, "workspace": True, "model": True, "usage": True, "limits": True, "resetTime": True})

    def _app_server_binary(self) -> str | None:
        for process in self._processes():
            if process["app_server"] and process["argv"]:
                candidate = process["argv"][0]
                if Path(candidate).exists(): return candidate
        return self.executable

    def _processes(self) -> list[dict]:
        result = []
        for entry in Path("/proc").iterdir():
            if not entry.name.isdigit(): continue
            pid = int(entry.name); raw = _proc_read(pid, "cmdline")
            if not raw: continue
            argv = [part for part in raw.split("\0") if part]
            if not argv: continue
            try: executable_name = Path(os.readlink(f"/proc/{pid}/exe")).name
            except (FileNotFoundError, PermissionError, OSError): executable_name = Path(argv[0]).name
            if executable_name in {"codex-code-mode-host", "codex-code-mode"} or Path(argv[0]).name in {"codex-code-mode-host", "codex-code-mode"}:
                continue
            command = " ".join(argv).lower()
            is_codex_binary = executable_name in {"codex", "codex-cli"} or Path(argv[0]).name in {"codex", "codex-cli"}
            is_vscode_codex = "openai.chatgpt" in command and "codex" in command
            if not is_codex_binary and not is_vscode_codex: continue
            try: cwd = os.readlink(f"/proc/{pid}/cwd")
            except (FileNotFoundError, PermissionError, OSError): cwd = None
            environment = _proc_read(pid, "environ") or ""
            environment_keys = {item.split("=", 1)[0] for item in environment.split("\0") if "=" in item}
            originator = next((item.split("=", 1)[1] for item in environment.split("\0") if item.startswith("CODEX_INTERNAL_ORIGINATOR_OVERRIDE=")), None)
            vscode = originator == "codex_vscode" or "vscode" in command or "--analytics-default-enabled" in argv or "VSCODE_PID" in environment_keys
            result.append({"pid": pid, "argv": argv, "cwd": cwd, "app_server": "app-server" in argv, "vscode": vscode, "originator": originator})
        return result

    def _recent_metadata(self, cwd: str | None, allow_any_cwd: bool = False, source: str | None = None) -> dict:
        if not cwd and not allow_any_cwd: return {}
        root = self.codex_home / "sessions"
        try: candidates = sorted(root.glob("**/*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)[:50]
        except OSError: return {}
        for path in candidates:
            try:
                if datetime.now(timezone.utc).timestamp() - path.stat().st_mtime > 86400: break
                with path.open(encoding="utf-8", errors="replace") as handle: record = json.loads(handle.readline())
                payload = record.get("payload", {})
                if record.get("type") == "session_meta" and (allow_any_cwd or payload.get("cwd") == cwd) and (source is None or payload.get("source") == source):
                    return {"session_id": payload.get("session_id") or payload.get("id"), "model": payload.get("model"), "source": payload.get("source"), "started_at": payload.get("timestamp"), "cli_version": payload.get("cli_version"), "cwd": payload.get("cwd")}
            except (OSError, json.JSONDecodeError, KeyError): continue
        return {}

    def _event_type_from_path(self, path: Path) -> str | None:
        try:
            with path.open("rb") as handle:
                handle.seek(0, 2); handle.seek(max(0, handle.tell() - 32768)); tail = handle.read().decode("utf-8", "replace")
        except OSError:
            return None
        event_type = None
        for line in tail.splitlines():
            try:
                record = json.loads(line); envelope = record.get("payload", {})
                if record.get("type") == "event_msg":
                    candidate = envelope.get("type")
                    if candidate in {"task_started", "turn_started", "item_started", "user_message", "task_complete", "turn_complete", "turn_aborted", "request_user_input"}:
                        event_type = candidate
                    # item_completed and token_count do not finish a turn.
                elif record.get("type") == "response_item":
                    item_type = envelope.get("type")
                    if item_type in {"reasoning", "message", "custom_tool_call", "function_call", "local_shell_call", "web_search_call"} and envelope.get("status") not in {"completed", "failed"}:
                        event_type = "item_started"
            except json.JSONDecodeError: continue
        return event_type

    def _recent_event_type(self, session_id: str | None) -> str | None:
        if not session_id: return None
        root = self.codex_home / "sessions"
        try: candidates = sorted(root.glob("**/*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)[:50]
        except OSError: return None
        for path in candidates:
            try:
                if datetime.now(timezone.utc).timestamp() - path.stat().st_mtime > 86400: break
                with path.open(encoding="utf-8", errors="replace") as handle: record = json.loads(handle.readline())
                payload = record.get("payload", {})
                if record.get("type") == "session_meta" and (payload.get("session_id") or payload.get("id")) == session_id:
                    return self._event_type_from_path(path)
            except (OSError, json.JSONDecodeError, KeyError): continue
        return None

    def _account_data(self) -> tuple[dict | None, dict | None]:
        """Read authenticated account data through a short-lived local app-server client."""
        binary = self._app_server_binary()
        if not binary: return None, None
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "vox-sentry", "version": "0.1.0"}}},
            {"jsonrpc": "2.0", "method": "initialized", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "account/rateLimits/read", "params": None},
            {"jsonrpc": "2.0", "id": 3, "method": "account/usage/read", "params": None},
        ]
        environment = os.environ.copy(); environment["CODEX_HOME"] = str(self.codex_home)
        process = None
        responses: dict[int, dict] = {}
        try:
            process = subprocess.Popen([binary, "app-server", "--listen", "stdio://"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1, env=environment)
            assert process.stdin is not None and process.stdout is not None
            for request in requests:
                process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
            process.stdin.flush()
            selector = selectors.DefaultSelector(); selector.register(process.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + 8
            while len(responses) < 2 and time.monotonic() < deadline:
                ready = selector.select(max(0.05, deadline - time.monotonic()))
                if not ready: continue
                line = process.stdout.readline()
                if not line: break
                try: message = json.loads(line)
                except json.JSONDecodeError: continue
                if message.get("id") in {2, 3} and isinstance(message.get("result"), dict): responses[message["id"]] = message["result"]
            selector.close()
        except (OSError, subprocess.SubprocessError, AssertionError):
            return None, None
        finally:
            if process is not None:
                if process.poll() is None: process.terminate()
                try: process.wait(timeout=1)
                except subprocess.TimeoutExpired: process.kill()
        return responses.get(2), responses.get(3)

    def _local_token_usage(self) -> AgentUsage | None:
        database = self.codex_home / "state_5.sqlite"
        if not database.exists(): return None
        try:
            uri = f"file:{database}?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=0.2) as connection:
                total = connection.execute("SELECT COALESCE(SUM(tokens_used), 0) FROM threads").fetchone()[0]
            return AgentUsage(details={"source": "local_thread_state", "lifetimeThreadTokens": int(total), "limitsAvailable": False})
        except (OSError, sqlite3.Error, TypeError, ValueError):
            return None

    def _usage_from_account(self, rate_limits: dict | None, account_usage: dict | None) -> AgentUsage | None:
        rate = rate_limits.get("rateLimits") if isinstance(rate_limits, dict) else None
        if not rate and isinstance(rate_limits, dict):
            by_limit_id = rate_limits.get("rateLimitsByLimitId")
            if isinstance(by_limit_id, dict):
                rate = by_limit_id.get("codex") or next(iter(by_limit_id.values()), None)
        primary = rate.get("primary") if isinstance(rate, dict) else None
        secondary = rate.get("secondary") if isinstance(rate, dict) else None
        summary = account_usage.get("summary") if isinstance(account_usage, dict) else None
        daily = account_usage.get("dailyUsageBuckets") if isinstance(account_usage, dict) else None
        if not any((rate, summary, daily)): return None
        today = time.strftime("%Y-%m-%d", time.gmtime())
        today_bucket = next((bucket for bucket in (daily or []) if bucket.get("startDate") == today), None)
        latest_bucket = (daily or [])[-1] if daily else None
        details = {
            "source": "codex_app_server",
            "planType": rate.get("planType") if isinstance(rate, dict) else None,
            "primary": primary,
            "secondary": secondary,
            "rateLimitReachedType": rate.get("rateLimitReachedType") if isinstance(rate, dict) else None,
            "spendControlReached": rate.get("spendControlReached") if isinstance(rate, dict) else None,
            "lifetimeTokens": summary.get("lifetimeTokens") if isinstance(summary, dict) else None,
            "todayTokens": today_bucket.get("tokens") if isinstance(today_bucket, dict) else None,
            "latestDailyTokens": latest_bucket.get("tokens") if isinstance(latest_bucket, dict) else None,
            "latestDailyDate": latest_bucket.get("startDate") if isinstance(latest_bucket, dict) else None,
            "peakDailyTokens": summary.get("peakDailyTokens") if isinstance(summary, dict) else None,
            "limitsAvailable": bool(rate),
        }
        return AgentUsage(primary.get("usedPercent") if isinstance(primary, dict) else None, secondary.get("usedPercent") if isinstance(secondary, dict) else None, primary.get("resetsAt") if isinstance(primary, dict) else None, details)

    def get_usage(self) -> AgentUsage | None:
        now = time.monotonic()
        if now - self._account_cache_at < 60: return self._account_cache
        self._account_cache_at = now
        self._account_cache = None
        rate_limits, account_usage = self._account_data()
        self._account_cache = self._usage_from_account(rate_limits, account_usage) or self._local_token_usage()
        return self._account_cache

    def _active_rollout(self, pid: int) -> tuple[dict, str | None]:
        """Read metadata and event envelope from rollout files held open by a live process.

        Only the record type is retained from the tail; message/content fields are discarded.
        """
        paths = []
        try:
            for fd in Path(f"/proc/{pid}/fd").iterdir():
                try: target = os.readlink(fd)
                except OSError: continue
                if target.endswith(".jsonl"): paths.append(Path(target))
        except OSError: return {}, None
        for path in sorted(set(paths), key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True):
            try:
                with path.open(encoding="utf-8", errors="replace") as handle: first = json.loads(handle.readline())
                payload = first.get("payload", {})
                metadata = {"session_id": payload.get("session_id") or payload.get("id"), "model": payload.get("model"), "source": payload.get("source"), "started_at": payload.get("timestamp"), "cli_version": payload.get("cli_version"), "cwd": payload.get("cwd")}
                event_type = self._event_type_from_path(path)
                return metadata, event_type
            except (OSError, json.JSONDecodeError): continue
        return {}, None

    def get_sessions(self) -> list[AgentSession]:
        processes = self._processes()
        if not processes: return []
        sessions = []
        for process in processes:
            metadata, event_type = self._active_rollout(process["pid"])
            expected_source = "vscode" if process["vscode"] else "cli"
            metadata = {**self._recent_metadata(process["cwd"], source=expected_source), **metadata}
            if not metadata.get("session_id"):
                # The systemd sandbox may hide /proc/<pid>/cwd and /proc/<pid>/fd
                # even though the session files themselves are readable. Use the
                # newest metadata for the matching frontend as a fallback for
                # both terminal CLI and VS Code app-server sessions.
                metadata = {**self._recent_metadata(None, allow_any_cwd=True, source=expected_source), **metadata}
            if event_type is None:
                event_type = self._recent_event_type(metadata.get("session_id"))
            source = SessionSource.VSCODE if process["vscode"] else SessionSource.CLI
            status = {
                "task_started": AgentStatus.THINKING,
                "turn_started": AgentStatus.THINKING,
                "item_started": AgentStatus.WORKING,
                "user_message": AgentStatus.THINKING,
                "task_complete": AgentStatus.IDLE,
                "turn_complete": AgentStatus.IDLE,
                "item_completed": AgentStatus.IDLE,
                "turn_aborted": AgentStatus.ERROR,
                "request_user_input": AgentStatus.WAITING,
            }.get(event_type, AgentStatus.IDLE)
            session_id = metadata.get("session_id") or f"codex-{process['pid']}"
            if any(session.id == session_id for session in sessions): session_id = f"{session_id}-{process['pid']}"
            workspace = metadata.get("cwd") or process["cwd"]
            sessions.append(AgentSession(session_id, self.id, source, status, process["pid"], workspace, Path(workspace).name if workspace else None, metadata.get("model"), metadata.get("started_at"), datetime.now(timezone.utc).isoformat(), metadata={"observation": "process", "appServer": process["app_server"], "eventType": event_type, "originator": process["originator"], "processKind": "vscode-app-server" if process["app_server"] else "cli"}))
        return sessions

    def get_status(self) -> AgentStatus:
        sessions = self.get_sessions()
        if not self.detect() or not sessions: return AgentStatus.OFFLINE
        usage = self.get_usage()
        details = usage.details if usage else {}
        primary = details.get("primary") if isinstance(details, dict) else None
        secondary = details.get("secondary") if isinstance(details, dict) else None
        if (
            details.get("rateLimitReachedType")
            or details.get("spendControlReached")
            or any(isinstance(window, dict) and (window.get("usedPercent") or 0) >= 100 for window in (primary, secondary))
        ):
            return AgentStatus.RATE_LIMITED
        for status in (AgentStatus.ERROR, AgentStatus.WAITING, AgentStatus.WORKING, AgentStatus.THINKING):
            if any(session.status == status for session in sessions): return status
        return AgentStatus.IDLE
