# Roadmap

The first implementation milestone is complete. The repository now includes the Core, protocol v1,
daemon/D-Bus service, CLI, systemd integration, GNOME indicator and Preferences UI, six local
providers, multi-session observation, Codex and Antigravity usage/limits, desktop notifications,
validated custom audio, performance hardening and the EGO release workflow.

## Next phases

- Verified usage/limit adapters for Gemini, Copilot, Claude Code and OpenCode when stable local
  sources become available.
- A versioned provider adapter API for custom integrations.
- More provider-native event watching, authentication/quota diagnostics and restart recovery.
- Additional clients such as Waybar, KDE, TUI and JetBrains after the GNOME/D-Bus contract settles.
- Later: remote agents and hardware status lights.
