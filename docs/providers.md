# Providers

Providers implement `AgentProvider` from `vox_sentry/provider.py`. They report explicit capabilities
and must return only data they can observe. A provider exception is contained by Core and represented
as `UNKNOWN` plus a `provider.error` event.

The registry supports runtime registration. Built-in providers currently include:

- `codex`: CLI, VS Code app-server, local sessions and authenticated usage/limits.
- `gemini`: Gemini CLI and Gemini Code Assist/A2A processes, local session metadata and activity.
- `antigravity`: Antigravity hub/agent processes, workspace and activity.
- `copilot`: GitHub Copilot CLI and VS Code/agent process discovery.
- `claude`: Claude Code CLI and IDE process/session discovery.
- `opencode`: OpenCode CLI/server process and read-only local session database discovery.

These providers do not currently claim usage/limit capabilities because their local quota
interfaces are not stable enough to observe without inventing values. Future providers can be
added without changing the normalized Core model or extension.
