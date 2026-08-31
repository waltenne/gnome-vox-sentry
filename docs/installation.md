# Installation

This guide explains how to install the Vox Sentry daemon and the GNOME Shell extension as a local
user. Vox Sentry is not a hosted service: provider discovery, status normalization, usage reads and
notifications stay on the machine.

## Table of contents

- [Requirements](#requirements)
- [Install from the repository](#install-from-the-repository)
- [Start and enable the daemon](#start-and-enable-the-daemon)
- [Install the EGO package](#install-the-ego-package)
- [Verify the installation](#verify-the-installation)
- [Audio codecs](#audio-codecs)
- [Uninstall](#uninstall)
- [Troubleshooting](#troubleshooting)

## Requirements

- GNOME Shell 46, the version declared by `gnome-extension/metadata.json`;
- Python 3.10 or newer;
- a GNOME session with the user D-Bus and systemd user services;
- the local provider CLI or application for each provider you want to monitor.

For custom notification sounds, install the GStreamer introspection data and common plugins:

```bash
sudo apt install gir1.2-gst-plugins-base-1.0 gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav
```

## Install from the repository

Clone the repository and run the user-scoped installer:

```bash
git clone https://github.com/waltenne/gnome-vox-sentry.git
cd gnome-vox-sentry
./install.sh
```

The installer creates the daemon environment at
`~/.local/share/gnome-vox-sentry/venv`, installs the CLI and daemon, copies the GNOME extension and
user systemd unit, and creates `vox-sentry`/`vox-sentryd` links under `~/.local/bin`.

## Start and enable the daemon

```bash
systemctl --user daemon-reload
systemctl --user enable --now vox-sentryd
gnome-extensions enable vox-sentry@gnome-vox-sentry
```

On Wayland, log out and back in once if GNOME cannot discover the extension immediately. The
Preferences window is opened from the indicator's **Settings** item.

## Install the EGO package

The reviewable extension-only package can be built locally:

```bash
./pack-ego.sh dist
./scripts/validate-ego-package.sh \
  dist/vox-sentry@gnome-vox-sentry.shell-extension.zip
gnome-extensions install --force \
  dist/vox-sentry@gnome-vox-sentry.shell-extension.zip
```

The package contains the GJS client, Preferences, schema, stylesheet, required JavaScript modules
and license. The Python daemon is intentionally installed separately.

## Verify the installation

```bash
systemctl --user is-active vox-sentryd
gnome-extensions info vox-sentry@gnome-vox-sentry
vox-sentry status --json
vox-sentry providers
```

The indicator shows **Offline** when the daemon is unavailable and **Unknown** when a provider
cannot provide a reliable state. These states are diagnostics, not fabricated activity.

## Audio codecs

Custom sounds officially support MP3, OGG, OGA, WAV and FLAC. All formats share a maximum duration
of 10 seconds and a maximum size of 5 MB. GStreamer validates the stream and must have a decoder
for the selected format; the file extension alone is never sufficient.

## Uninstall

Disable the extension and stop the user service before removing the installed files:

```bash
gnome-extensions disable vox-sentry@gnome-vox-sentry || true
systemctl --user disable --now vox-sentryd
rm -rf ~/.local/share/gnome-shell/extensions/vox-sentry@gnome-vox-sentry
rm -rf ~/.local/share/gnome-vox-sentry
rm -f ~/.local/bin/vox-sentry ~/.local/bin/vox-sentryd
rm -f ~/.config/systemd/user/vox-sentryd.service
systemctl --user daemon-reload
```

The configuration at `~/.config/gnome-vox-sentry/config.json` and the GSettings schema values are
not removed automatically, so they can be retained for a later reinstall or removed deliberately.

## Troubleshooting

- **Offline indicator:** check `systemctl --user status vox-sentryd` and inspect the user journal
  with `journalctl --user -u vox-sentryd`.
- **Provider not listed:** verify that its local CLI/application is installed and that the provider
  is enabled in the Providers page or daemon configuration.
- **No sound:** install the GStreamer packages above, then use the Sounds page Preview action.
- **Extension not found:** confirm the UUID and restart the GNOME session on Wayland.
- **Usage unavailable:** the provider must expose an authenticated and verifiable local usage
  source; Vox Sentry intentionally does not invent quota values.
