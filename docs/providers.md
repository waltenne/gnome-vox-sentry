# Providers

Providers implement `AgentProvider` from `vox_sentry/provider.py`. They report explicit capabilities
and must return only data they can observe. A provider exception is contained by Core and represented
as `UNKNOWN` plus a `provider.error` event.

The registry supports runtime registration. Built-in providers currently include:

- `codex`: CLI, VS Code app-server, local sessions and authenticated usage/limits.
- `gemini`: Gemini CLI and Gemini Code Assist/A2A processes, local session metadata and activity.
- `antigravity`: Antigravity hub/agent processes, workspace/activity and authenticated Cloud Code
  quota windows when the account exposes them.
- `copilot`: GitHub Copilot CLI and VS Code/agent process discovery.
- `claude`: Claude Code CLI and IDE process/session discovery.
- `opencode`: OpenCode CLI/server process and read-only local session database discovery.

Providers only claim usage/limit capabilities when they have a supported source. Antigravity uses
the authenticated Cloud Code quota endpoints and omits usage when authentication or entitlement
is unavailable; it never creates placeholder values. Future providers can be added without
changing the normalized Core model or extension.
