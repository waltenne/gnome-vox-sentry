from __future__ import annotations

import logging

from .models import ProviderInfo
from .provider import AgentProvider

LOG = logging.getLogger(__name__)


class ProviderRegistry:
    def __init__(self) -> None: self._providers: dict[str, AgentProvider] = {}
    def register(self, provider: AgentProvider) -> None:
        if provider.id in self._providers: raise ValueError(f"provider already registered: {provider.id}")
        self._providers[provider.id] = provider
    def get(self, provider_id: str) -> AgentProvider: return self._providers[provider_id]
    def all(self) -> list[AgentProvider]: return list(self._providers.values())

    def inspect(self, enabled: set[str] | None = None) -> list[ProviderInfo]:
        result = []
        for provider in self.all():
            try:
                available, error = provider.detect(), None
                capabilities = provider.get_capabilities()
            except Exception as exc:
                LOG.exception("provider inspection failed: %s", provider.id)
                available, error, capabilities = False, str(exc), provider.get_capabilities()
            result.append(ProviderInfo(provider.id, provider.name, available, available and (enabled is None or provider.id in enabled), provider.version, capabilities, error))
        return result
