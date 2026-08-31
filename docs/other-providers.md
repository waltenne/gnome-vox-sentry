# Copilot, Claude Code and OpenCode providers

These providers use conservative local observations. They never call provider APIs and do not
parse prompts, answers, source files or credentials.

## Copilot

The provider recognizes `copilot`, `github-copilot` and the supported Node package process. It
classifies sessions launched by VS Code when the process exposes VS Code/Copilot environment
markers. CLI sessions are reported separately. Copilot session metadata is used only for file age
and session identity; cached user messages are not read. The VS Code shim is never invoked with a
version command because that command can open an installation prompt.

## Claude Code

The provider recognizes the `claude` executable and Claude Code's Node runtime. It distinguishes
the CLI from IDE sessions using IDE environment markers and `--ide`. Live session files under
`~/.claude/projects` are used only as activity evidence; JSONL message contents are not parsed.

## OpenCode

The provider recognizes the CLI, TUI, ACP and server processes. It reads the local SQLite database
at `~/.local/share/opencode/opencode.db` in read-only mode and selects the session matching the
process working directory. Only session ID, directory, timestamps and model are retained. Recent
session updates indicate working; a live interactive process with no recent update is idle.

None of the three providers exposes usage or quota data yet. The GNOME menu therefore shows
`Consumption: Unavailable` for them rather than displaying guessed limits.
