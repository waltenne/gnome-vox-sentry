# Codex provider investigation

Investigation date: 2026-08-30. The local installation reported `codex-cli 0.151.0`.

| Signal | Source / maturity | v0.1 behavior |
|---|---|---|
| Installation/version | `codex --version`, executable lookup / STABLE | Implemented |
| Live process and PID | Linux `/proc` / STABLE | Implemented |
| CLI sessions | `codex`/`codex-cli` process / STABLE | Implemented |
| VS Code extension/chat | bundled `codex app-server`, VS Code originator/environment / observed | Implemented |
| Workspace | `/proc/<pid>/cwd` / STABLE | Implemented |
| Session metadata | first `session_meta` JSONL record under `$CODEX_HOME/sessions` / STABLE in observed install | Implemented; content is never read |
| Model/source | session metadata / STABLE in observed install | Implemented when present |
| Fine-grained state | Codex app-server notifications / EXPERIMENTAL | Process and rollout event observations for CLI and VS Code; idle is used when no active event is available |
| Events | app-server JSON-RPC notifications / EXPERIMENTAL | Not connected |
| Usage/limits/reset | `account/rateLimits/read`, `account/usage/read` / EXPERIMENTAL and authenticated | Implemented through a short-lived local app-server client; unavailable values remain omitted |
| Error/rate-limit state | app-server account response / EXPERIMENTAL | `RATE_LIMITED` is reported when a window is exhausted or Codex reports a quota block; session errors still depend on rollout observations |

The provider uses the app-server only for the authenticated account summaries needed for usage and
limits. Session state continues to come from safe process/metadata observations, because the
long-lived event adapter is still outside this provider version.
