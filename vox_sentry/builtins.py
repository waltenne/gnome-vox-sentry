from providers.antigravity import AntigravityProvider
from providers.claude import ClaudeProvider
from providers.codex import CodexProvider
from providers.copilot import CopilotProvider
from providers.gemini import GeminiProvider
from providers.opencode import OpenCodeProvider

from .registry import ProviderRegistry


def default_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(CodexProvider())
    registry.register(GeminiProvider())
    registry.register(AntigravityProvider())
    registry.register(CopilotProvider())
    registry.register(ClaudeProvider())
    registry.register(OpenCodeProvider())
    return registry
