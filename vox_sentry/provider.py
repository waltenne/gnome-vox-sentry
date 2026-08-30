"""Provider contract. Scheduling and isolation belong to the daemon/Core boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from .models import AgentEvent, AgentSession, AgentStatus, AgentUsage, ProviderCapabilities


class ProviderError(RuntimeError):
    """A recoverable provider failure."""


class AgentProvider(ABC):
    id: str
    name: str
    version: str | None = None

    @abstractmethod
    def detect(self) -> bool: ...

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities: ...

    @abstractmethod
    def get_status(self) -> AgentStatus: ...

    @abstractmethod
    def get_sessions(self) -> list[AgentSession]: ...

    def get_usage(self) -> AgentUsage | None:
        return None

    def start_watching(self, callback: Callable[[AgentEvent], None]) -> None:
        del callback

    def stop_watching(self) -> None:
        pass
