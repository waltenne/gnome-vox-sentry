from providers.mock import MockProvider, MockProviderMultipleSessions
from vox_sentry.aggregate import aggregate_status
from vox_sentry.core import VoxSentryCore
from vox_sentry.models import AgentStatus
from vox_sentry.provider import ProviderError
from vox_sentry.registry import ProviderRegistry


def test_aggregate_priority_is_provider_neutral():
    assert aggregate_status([AgentStatus.WORKING, AgentStatus.WAITING]) == AgentStatus.WAITING
    assert aggregate_status([AgentStatus.WORKING, AgentStatus.ERROR]) == AgentStatus.ERROR


def test_multiple_providers_and_sessions():
    registry = ProviderRegistry(); registry.register(MockProvider("codex", AgentStatus.WORKING)); registry.register(MockProvider("claude", AgentStatus.WAITING)); registry.register(MockProviderMultipleSessions())
    config = {"providerMode": "multi", "providers": {"codex": {"enabled": True}, "claude": {"enabled": True}, "mock-multiple": {"enabled": True}}}
    snapshot = VoxSentryCore(registry, config).refresh()
    assert snapshot.status == AgentStatus.WAITING
    assert len(snapshot.sessions) == 4


def test_provider_crash_becomes_unknown():
    class Broken(MockProvider):
        def get_sessions(self): raise ProviderError("boom")
    registry = ProviderRegistry(); registry.register(Broken("broken", AgentStatus.WORKING))
    assert VoxSentryCore(registry, {"providerMode": "multi", "providers": {"broken": {"enabled": True}}}).refresh().status == AgentStatus.UNKNOWN
