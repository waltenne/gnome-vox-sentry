"""Antigravity IDE/CLI observer based on its local agent process tree."""

from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from providers.google_process import descendants, open_files, process_snapshot, workspace_name
from vox_sentry.models import (
    AgentSession,
    AgentStatus,
    AgentUsage,
    ProviderCapabilities,
    SessionSource,
)
from vox_sentry.provider import AgentProvider


class AntigravityProvider(AgentProvider):
    id, name = "antigravity", "Antigravity"
    # A hub is a long-lived transport process.  Its log can remain open after
    # the chat has been closed, so old log entries must not keep a session
    # visible forever.
    _RECENT_ACTIVITY_SECONDS = 30

    _USAGE_CACHE_SECONDS = 60
    _CLOUD_CODE_HOSTS = (
        "https://daily-cloudcode-pa.googleapis.com",
        "https://cloudcode-pa.googleapis.com",
    )

    def __init__(self, executable: str | None = None, gemini_home: Path | None = None) -> None:
        # Current Linux builds expose the backend as agy; older launchers expose
        # antigravity. Detection also works when the binary is not on PATH but is
        # already running.
        self.executable = executable or shutil.which("agy") or shutil.which("antigravity")
        self.gemini_home = gemini_home or (Path.home() / ".gemini")
        self.version = self._version_from_binary()
        self._usage_cache: AgentUsage | None = None
        self._usage_cache_at = 0.0

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
        return ProviderCapabilities(
            {
                "status": True,
                "sessions": True,
                "workspace": True,
                "model": True,
                "usage": True,
                "limits": True,
                "resetTime": True,
            }
        )

    def _credentials(self) -> dict | None:
        """Read an existing Antigravity/Gemini credential without starting login.

        Antigravity stores credentials in the desktop keyring. The CLI fallback
        used by the current Linux package is the standard Gemini credential file.
        The token is used only in memory and is never logged or written by Vox
        Sentry.
        """
        secret_tool = shutil.which("secret-tool")
        if secret_tool:
            try:
                result = subprocess.run(
                    [secret_tool, "lookup", "service", "gemini", "username", "antigravity"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=False,
                )
                if result.returncode == 0 and result.stdout.strip():
                    value = json.loads(result.stdout)
                    if isinstance(value, dict):
                        return value.get("token", value)
            except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
                pass

        for path in (
            self.gemini_home / "antigravity-cli/antigravity-oauth-token",
            self.gemini_home / "oauth_creds.json",
        ):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict):
                return value.get("token", value)
        return None

    def _access_token(self) -> str | None:
        credentials = self._credentials()
        if not isinstance(credentials, dict):
            return None
        token = credentials.get("access_token")
        expiry = credentials.get("expiry_date", credentials.get("expiry"))
        if not isinstance(token, str) or not token:
            return None
        if isinstance(expiry, (int, float)):
            # Gemini CLI uses milliseconds; some keyring payloads use seconds.
            expiry_seconds = expiry / 1000 if expiry > 10_000_000_000 else expiry
            if expiry_seconds <= time.time() + 30:
                return None
        return token

    def _post_json(self, endpoint: str, token: str, payload: dict) -> dict | None:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "antigravity",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                value = json.loads(response.read(1_000_000).decode("utf-8"))
            return value if isinstance(value, dict) else None
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
            return None

    @staticmethod
    def _fraction(value: object) -> float | None:
        try:
            fraction = float(value)
        except (TypeError, ValueError):
            return None
        return fraction if 0 <= fraction <= 1 else None

    @staticmethod
    def _quota_window(bucket: dict) -> dict | None:
        fraction = AntigravityProvider._fraction(
            bucket.get("remainingFraction", bucket.get("remaining_fraction"))
        )
        if fraction is None:
            return None
        reset = bucket.get("resetTime", bucket.get("reset_time"))
        bucket_id = str(bucket.get("bucketId", bucket.get("bucket_id", bucket.get("id", "")))).lower()
        window_name = str(bucket.get("window", "")).lower()
        return {
            "usedPercent": round((1 - fraction) * 100, 1),
            "remainingPercent": round(fraction * 100, 1),
            "resetTime": reset if isinstance(reset, str) and reset else None,
            "windowDurationMins": 300 if "5h" in bucket_id or window_name == "5h" else 10080,
        }

    def _usage_from_summary(self, response: dict) -> AgentUsage | None:
        groups = response.get("groups")
        if not isinstance(groups, list):
            return None
        windows: dict[str, dict] = {}
        for group in groups:
            if not isinstance(group, dict):
                continue
            group_name = str(group.get("displayName", group.get("display_name", group.get("name", "")))).lower()
            family = "thirdParty" if any(word in group_name for word in ("claude", "gpt", "third")) else "gemini"
            for bucket in group.get("buckets", []):
                if not isinstance(bucket, dict):
                    continue
                window = self._quota_window(bucket)
                if window is None:
                    continue
                bucket_id = str(bucket.get("bucketId", bucket.get("bucket_id", bucket.get("id", "")))).lower()
                bucket_window = str(bucket.get("window", "")).lower()
                window_name = "session" if "5h" in bucket_id or "session" in bucket_id or bucket_window == "5h" else "weekly"
                windows[f"{family}-{window_name}"] = window
        if not windows:
            return None
        primary = windows.get("gemini-session") or windows.get("thirdParty-session")
        secondary = windows.get("gemini-weekly") or windows.get("thirdParty-weekly")
        if primary is None and secondary is None:
            return None
        reset_at = None
        if primary and primary.get("resetTime"):
            try:
                reset_at = int(datetime.fromisoformat(primary["resetTime"].replace("Z", "+00:00")).timestamp())
            except ValueError:
                pass
        return AgentUsage(
            primary.get("usedPercent") if primary else None,
            secondary.get("usedPercent") if secondary else None,
            reset_at,
            {
                "source": "antigravity_cloud_code",
                "primary": primary,
                "secondary": secondary,
                "windows": windows,
                "limitsAvailable": True,
            },
        )

    def _usage_from_cli(self) -> AgentUsage | None:
        """Ask agy for its official structured usage view.

        This is the most reliable source because agy owns authentication and the
        current quota protocol. It also works for accounts where a third-party
        direct request to the Cloud Code quota endpoint is denied.
        """
        if not self.executable:
            return None
        try:
            result = subprocess.run(
                [self.executable, "-p", "/usage", "--output-format", "json"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        # Keep parsing bounded and tolerate informational lines emitted by older
        # versions before the JSON result.
        for line in reversed(result.stdout.splitlines()[-10:]):
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            command = payload.get("command") if isinstance(payload, dict) else None
            data = command.get("data") if isinstance(command, dict) else None
            if not isinstance(data, dict) or not isinstance(data.get("groups"), list):
                continue
            usage = self._usage_from_summary(data)
            if usage:
                usage.details["source"] = "antigravity_cli_usage"
                return usage
        return None

    def _usage_from_models(self, response: dict) -> AgentUsage | None:
        models = response.get("models")
        if not isinstance(models, dict):
            return None
        quotas = []
        for model_id, model in models.items():
            if not isinstance(model, dict):
                continue
            quota = model.get("quotaInfo", model.get("quota_info"))
            if not isinstance(quota, dict):
                continue
            window = self._quota_window({**quota, "bucketId": model_id})
            if window is not None:
                quotas.append({"model": model_id, "displayName": model.get("displayName"), **window})
        if not quotas:
            return None
        quotas.sort(key=lambda item: (item["remainingPercent"], item["model"]))
        primary = quotas[0]
        return AgentUsage(
            primary["usedPercent"],
            None,
            None,
            {
                "source": "antigravity_cloud_code_models",
                "primary": primary,
                "modelQuotas": quotas,
                "limitsAvailable": True,
            },
        )

    def get_usage(self) -> AgentUsage | None:
        now = time.monotonic()
        if now - self._usage_cache_at < self._USAGE_CACHE_SECONDS:
            return self._usage_cache
        self._usage_cache_at = now
        self._usage_cache = None
        usage = self._usage_from_cli()
        if usage:
            self._usage_cache = usage
            return usage
        token = self._access_token()
        if not token:
            return None
        for host in self._CLOUD_CODE_HOSTS:
            load = self._post_json(
                f"{host}/v1internal:loadCodeAssist",
                token,
                {"metadata": {"ideType": "ANTIGRAVITY"}},
            )
            if not load:
                continue
            project = load.get("cloudaicompanionProject")
            summary = self._post_json(
                f"{host}/v1internal:retrieveUserQuotaSummary",
                token,
                {"project": project} if isinstance(project, str) and project else {},
            )
            usage = self._usage_from_summary(summary) if summary else None
            if usage:
                self._usage_cache = usage
                return usage
            models = self._post_json(
                f"{host}/v1internal:fetchAvailableModels",
                token,
                {"project": project} if isinstance(project, str) and project else {},
            )
            usage = self._usage_from_models(models) if models else None
            if usage:
                self._usage_cache = usage
                return usage
        return None

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

    def get_status(self, sessions: list[AgentSession] | None = None) -> AgentStatus:
        sessions = self.get_sessions() if sessions is None else sessions
        if not self.detect() or not sessions:
            return AgentStatus.OFFLINE
        if any(session.status == AgentStatus.WORKING for session in sessions):
            return AgentStatus.WORKING
        return AgentStatus.IDLE
