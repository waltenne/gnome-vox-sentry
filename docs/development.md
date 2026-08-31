# Development

```bash
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest
python -m vox_sentry.daemon --once
vox-sentry status --json
```

For a live desktop session, install PyGObject from the distribution packages (the
`--system-site-packages` venv option makes Gio/GLib available), then install the
`gnome-extension` directory under
`~/.local/share/gnome-shell/extensions/vox-sentry@gnome-vox-sentry`.

For an end-user installation, run `./install.sh`. It creates an isolated virtualenv under
`~/.local/share/gnome-vox-sentry/venv`, installs the extension and user systemd unit, and avoids
Debian/Ubuntu PEP 668 environments. The unit explicitly includes `~/.local/bin` in `PATH` so a
Codex installed there is discoverable by the daemon.

## Supported GNOME version

The submitted extension currently targets **GNOME Shell 46** only. This is the version declared in
`gnome-extension/metadata.json` and the version used for the publication checks. The extension uses
the GNOME 45+ GJS lifecycle (`enable()`/`disable()`), GSettings, St, Gio and the session D-Bus.
Python 3.10+ is required for the daemon and CLI.

Before adding another Shell version, test a clean login session, enable/disable/re-enable lifecycle,
Preferences, D-Bus-unavailable behavior, notifications, sound preview and the EGO package on that
version. Then update the metadata and compatibility documentation together.
