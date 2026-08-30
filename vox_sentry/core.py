from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from .aggregate import aggregate_status
from .config import load_config
from .models import AgentEvent, AgentSession, AgentStatus, AgentUsage, Snapshot
from .protocol import PROTOCOL_VERSION
from .registry import ProviderRegistry

LOG = logging.getLogger(__name__)


class VoxSentryCore:
    def __init__(self, registry: ProviderRegistry, config: dict | None = None) -> None:
        self.registry, self.config = registry, config or load_config()
        self.sessions: dict[str, AgentSession] = {}
        self.usage: dict[str, AgentUsage] = {}
        self._listeners: list[Callable[[AgentEvent], None]] = []
        self._last_snapshot: Snapshot | None = None

    def add_listener(self, listener: Callable[[AgentEvent], None]) -> None: self._listeners.append(listener)
    def emit(self, event: AgentEvent) -> None:
        for listener in tuple(self._listeners):
            try: listener(event)
            except Exception: LOG.exception("event listener failed")

    def _enabled(self) -> set[str] | None:
        mode, providers = self.config.get("providerMode", "auto"), self.config.get("providers", {})
        enabled = {key for key, value in providers.items() if isinstance(value, dict) and value.get("enabled", True)}
        if mode == "manual": return {self.config["provider"]} if self.config.get("provider") else enabled
        return enabled if mode == "multi" else None

    def refresh(self) -> Snapshot:
        infos, statuses, next_sessions, next_usage = self.registry.inspect(self._enabled()), [], {}, {}
        for info in infos:
            if not info.active:
                info.status = AgentStatus.OFFLINE
                statuses.append(AgentStatus.OFFLINE); continue
            provider = self.registry.get(info.id)
            try:
                for session in provider.get_sessions(): next_sessions[session.id] = session
                info.status = provider.get_status()
                statuses.append(info.status)
                usage = provider.get_usage()
                if usage is not None: next_usage[provider.id] = usage
            except Exception as exc:
                LOG.exception("provider refresh failed: %s", provider.id)
                info.status = AgentStatus.UNKNOWN
                statuses.append(AgentStatus.UNKNOWN)
                self.emit(AgentEvent("provider.error", provider.id, payload={"error": str(exc)}))
        old_ids, new_ids = set(self.sessions), set(next_sessions)
        for session_id in new_ids - old_ids:
            session = next_sessions[session_id]; self.emit(AgentEvent("session.started", session.provider, session_id, session.status))
        for session_id in old_ids - new_ids:
            old = self.sessions[session_id]; self.emit(AgentEvent("session.ended", old.provider, session_id, AgentStatus.COMPLETED))
        self.sessions, self.usage = next_sessions, next_usage
        snapshot = Snapshot(PROTOCOL_VERSION, aggregate_status(statuses), infos, sorted(next_sessions.values(), key=lambda s: s.id), next_usage, datetime.now(timezone.utc).isoformat())
        if self._last_snapshot and snapshot.status != self._last_snapshot.status: self.emit(AgentEvent("status.changed", "core", status=snapshot.status))
        self._last_snapshot = snapshot
        return snapshot

    def get_status(self) -> Snapshot: return self._last_snapshot or self.refresh()
    def reload(self) -> Snapshot:
        self.config = load_config(); return self.refresh()
