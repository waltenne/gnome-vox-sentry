"""Provider-neutral data models exposed by Vox Sentry Core."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class AgentStatus(str, Enum):
    OFFLINE = "OFFLINE"
    IDLE = "IDLE"
    THINKING = "THINKING"
    WORKING = "WORKING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    UNKNOWN = "UNKNOWN"


class SessionSource(str, Enum):
    CLI = "cli"
    VSCODE = "vscode"
    JETBRAINS = "jetbrains"
    DESKTOP = "desktop"
    REMOTE = "remote"
    CUSTOM = "custom"


CAPABILITIES = ("status", "sessions", "workspace", "model", "usage", "limits", "resetTime", "events", "tools", "currentTask")


@dataclass(frozen=True)
class ProviderCapabilities:
    values: dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", {name: bool(self.values.get(name, False)) for name in CAPABILITIES})

    def to_dict(self) -> dict[str, bool]:
        return dict(self.values)


@dataclass
class AgentUsage:
    session_percent: float | None = None
    limit_percent: float | None = None
    reset_at: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"sessionPercent": self.session_percent, "limitPercent": self.limit_percent, "resetAt": self.reset_at, "details": dict(self.details)}


@dataclass
class AgentSession:
    id: str
    provider: str
    source: SessionSource | str
    status: AgentStatus
    pid: int | None = None
    workspace: str | None = None
    project_name: str | None = None
    model: str | None = None
    started_at: str | None = None
    updated_at: str | None = None
    usage: AgentUsage | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["source"] = self.source.value if isinstance(self.source, Enum) else self.source
        result["status"] = self.status.value if isinstance(self.status, Enum) else self.status
        if self.usage is not None:
            result["usage"] = self.usage.to_dict()
        result["projectName"] = result.pop("project_name")
        result["startedAt"] = result.pop("started_at")
        result["updatedAt"] = result.pop("updated_at")
        return result


@dataclass
class ProviderInfo:
    id: str
    name: str
    available: bool
    active: bool
    version: str | None = None
    capabilities: ProviderCapabilities = field(default_factory=ProviderCapabilities)
    error: str | None = None
    status: AgentStatus = AgentStatus.OFFLINE

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "available": self.available, "active": self.active, "status": self.status.value, "version": self.version, "capabilities": self.capabilities.to_dict(), "error": self.error}


@dataclass
class AgentEvent:
    type: str
    provider: str
    session_id: str | None = None
    status: AgentStatus | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "provider": self.provider, "sessionId": self.session_id, "status": self.status.value if isinstance(self.status, Enum) else self.status, "payload": dict(self.payload)}


@dataclass
class Snapshot:
    protocol_version: int
    status: AgentStatus
    providers: list[ProviderInfo]
    sessions: list[AgentSession]
    usage: dict[str, AgentUsage] = field(default_factory=dict)
    generated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"protocolVersion": self.protocol_version, "status": self.status.value, "providers": [p.to_dict() for p in self.providers], "sessions": [s.to_dict() for s in self.sessions], "usage": {k: v.to_dict() for k, v in self.usage.items()}, "generatedAt": self.generated_at}
