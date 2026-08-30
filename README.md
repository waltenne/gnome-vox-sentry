# gnome-vox-sentry

Project repository: https://github.com/waltenne/gnome-vox-sentry

Vox Sentry is a local-first, privacy-first sentry for coding agents running on Linux/GNOME. It
discovers agents, normalizes their state and presents a discreet top-bar indicator. Codex, Gemini,
Antigravity, Copilot, Claude and OpenCode are supported providers; the Core, protocol, daemon and
GNOME client are provider-neutral.

The project is distributed under the GNU GPL-2.0-or-later; see [LICENSE](LICENSE).

## Status

The v0.1 implementation detects Codex CLI/VS Code, Gemini CLI/VS Code, Antigravity, GitHub Copilot,
Claude Code and OpenCode local processes. It reports process, PID, workspace and session metadata.
Activity is inferred from provider-local session metadata and live process state. Codex additionally
exposes authenticated usage and rate-limit windows. The UI never fabricates unavailable values, so
providers without a stable local usage API are shown as unavailable.

## Layout

```text
vox_sentry/              normalized models, registry, aggregation, protocol, daemon and CLI
providers/codex/         Codex discovery, sessions and usage translation
providers/gemini/        Gemini CLI/VS Code discovery and session translation
providers/antigravity/   Antigravity hub/agent process-tree translation
providers/copilot/       GitHub Copilot CLI/VS Code discovery
providers/claude/        Claude Code CLI/IDE discovery
providers/opencode/      OpenCode CLI/server and local session translation
gnome-extension/         GJS indicator, Preferences, notifications and Sound Manager
vox_sentry/sound.py      shared audio validation policy and test/CLI boundary
tests/                   provider, audio validation and Codex boundary tests
docs/                    architecture, protocol and contributor guides
systemd/                 user service
```

## Quick start

```bash
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest
python -m vox_sentry.daemon --once
vox-sentry status
vox-sentry status --json
vox-sentry sessions
vox-sentry providers
```

For a user installation, run `./install.sh`. It creates an isolated virtualenv at
`~/.local/share/gnome-vox-sentry/venv`, installs the CLI/daemon there, installs the extension and
user systemd unit, and avoids the PEP 668 `externally-managed-environment` error found on Debian and
Ubuntu. It also adds `vox-sentry` and `vox-sentryd` symlinks under `~/.local/bin`.

Notification sound playback uses the GNOME/Linux GStreamer stack. On Debian/Ubuntu systems, make
sure the base introspection data and Good plugins are installed so OGG, OGA, WAV, FLAC and MP3
decoders are available:

```bash
sudo apt install gir1.2-gst-plugins-base-1.0 gstreamer1.0-plugins-good
```

Start `vox-sentryd` in a GNOME session for D-Bus clients. The daemon uses
`io.github.gnome_vox_sentry` and object `/io/github/gnome_vox_sentry`. Install the systemd unit to
`~/.config/systemd/user/`, run `systemctl --user daemon-reload`, then
`systemctl --user enable --now vox-sentryd`.

Enable the panel indicator with:

```bash
gnome-extensions enable vox-sentry@gnome-vox-sentry
```

GNOME Shell discovers user extensions at session startup. On Wayland, log out and back in once
after installation if `gnome-extensions` reports that the UUID does not exist.

To create the reviewable EGO bundle, use the explicit extension-only allowlist:

```bash
./pack-ego.sh dist
unzip -t dist/vox-sentry@gnome-vox-sentry.shell-extension.zip
```

The ZIP contains only the GJS extension, Preferences client, notification/sound modules,
stylesheet, GSettings XML and the project license. The daemon and its Python providers remain a separately installed
local prerequisite. See [docs/gnome/ego-review-checklist.md](docs/gnome/ego-review-checklist.md) and
[docs/gnome/ego-blockers.md](docs/gnome/ego-blockers.md) before submitting to EGO.

## Configuration

Configuration is JSON at `$XDG_CONFIG_HOME/gnome-vox-sentry/config.json` (normally
`~/.config/gnome-vox-sentry/config.json`). Data and cache paths are respectively under
`$XDG_DATA_HOME` and `$XDG_CACHE_HOME`. The default is `providerMode: auto`; `manual` and `multi`
are supported.

```bash
vox-sentry provider use auto
vox-sentry provider use codex
vox-sentry provider use gemini
vox-sentry provider use antigravity
vox-sentry provider use copilot
vox-sentry provider use claude
vox-sentry provider use opencode
vox-sentry provider use multi
vox-sentry provider enable codex
vox-sentry provider disable codex
```

In `auto` mode, all detected providers are monitored. The GNOME menu identifies live sessions by
provider and workspace. “Working” means a recent provider session update or an active agent process
was observed; an open interactive CLI is reported as “Idle” until it begins updating its local
session state.

The GNOME Preferences window includes a connected-provider filter, live status diagnostics and
notification sound settings. Custom sounds officially support MP3, OGG, OGA, WAV and FLAC. Every
format uses the same maximum duration of 10 seconds and maximum size of 5 MB. Files are checked by
MIME type, magic bytes, integrity, duration and actual decoder availability; the MP3 path uses
GStreamer and is not experimental.

## Privacy and security

No telemetry is implemented. The Codex provider reads executable/process metadata and only rollout
metadata/event types; prompts, answers, source code, file contents and credentials are not
transmitted or logged. Usage is requested from the local authenticated Codex app-server and only
the aggregate values needed by the indicator are retained. The daemon is local and the session bus
name is not a network API.

## Official Codex basis

The official Codex CLI documentation describes local repository work, `codex exec`, saved sessions
and the App Server. The App Server exposes JSON-RPC thread events and account rate-limit methods but
is experimental; the investigation and maturity table are in
[docs/codex-provider.md](docs/codex-provider.md).

See [docs/development.md](docs/development.md), [docs/creating-provider.md](docs/creating-provider.md)
and [docs/protocol.md](docs/protocol.md) for contributors and client authors.
