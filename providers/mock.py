"""Deterministic providers for tests and architecture demos."""

from vox_sentry.models import AgentSession, AgentStatus, ProviderCapabilities, SessionSource
from vox_sentry.provider import AgentProvider


class MockProvider(AgentProvider):
    def __init__(self, provider_id: str, status: AgentStatus, sessions: int = 1) -> None:
        self.id, self.name, self._status, self._sessions = provider_id, f"Mock {provider_id}", status, sessions

    def detect(self) -> bool: return True
    def get_capabilities(self) -> ProviderCapabilities: return ProviderCapabilities({"status": True, "sessions": True, "workspace": True, "model": True})
    def get_status(self, sessions: list[AgentSession] | None = None) -> AgentStatus:
        del sessions
        return self._status
    def get_sessions(self) -> list[AgentSession]:
        if self._status == AgentStatus.OFFLINE: return []
        return [AgentSession(f"{self.id}-{i}", self.id, SessionSource.CLI, self._status, workspace=f"/tmp/{self.id}/{i}", project_name=self.id, model="mock-model") for i in range(self._sessions)]


def MockProviderIdle(): return MockProvider("mock-idle", AgentStatus.IDLE)
def MockProviderWorking(): return MockProvider("mock-working", AgentStatus.WORKING)
def MockProviderWaiting(): return MockProvider("mock-waiting", AgentStatus.WAITING)
def MockProviderError(): return MockProvider("mock-error", AgentStatus.ERROR)
def MockProviderRateLimited(): return MockProvider("mock-rate-limited", AgentStatus.RATE_LIMITED)
def MockProviderMultipleSessions(): return MockProvider("mock-multiple", AgentStatus.WORKING, 2)
