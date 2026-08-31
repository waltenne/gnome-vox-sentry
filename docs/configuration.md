# Configuration

## Table of contents

- [Configuration categories](#configuration-categories)
- [Configuration screenshots](#configuration-screenshots)
- [Runtime configuration](#runtime-configuration)
- [Notification sound settings](#notification-sound-settings)

The GNOME preferences window uses a native Adwaita sidebar with five categories:

- **General**: provider mode, connected-provider filtering, session display, usage, limits, status
  color testing and automatic refresh interval.
- **Providers**: every supported provider with its live connection and status.
- **Notifications**: desktop notifications and notification simulation.
- **Sounds**: custom event audio, preview and format requirements.
- **About**: version, GNOME compatibility, privacy, repository and license.

The **Show only connected providers** option is enabled by default. Disable it to keep offline
providers visible in the indicator and compare their status. The Providers tab always lists all
providers, including offline ones, so detection can be diagnosed without changing the dropdown.

## Configuration categories

| Tab | Configuration | Default |
| --- | --- | --- |
| General | Provider mode, connected-only providers, multiple sessions, usage, limits, color test and refresh interval | Auto, connected-only on, multiple sessions on, usage/limits on, 2 seconds |
| Providers | Live connection, detected version and current status for every supported provider | Read-only diagnostics |
| Notifications | Desktop notifications and notification simulation | Notifications on |
| Sounds | Sound playback, event sounds, preview and validated audio formats | Sounds on; system fallback |
| About | Version, compatibility, privacy, repository and license | Informational |

The Preferences window is opened from the indicator's **Settings** item. It uses GSettings with the
schema `org.gnome.shell.extensions.vox-sentry`. The daemon uses a separate JSON configuration file
at `$XDG_CONFIG_HOME/gnome-vox-sentry/config.json`, so provider enablement and daemon scheduling do
not depend on the Preferences process.

## Configuration screenshots

The following captures document the current GNOME dark-theme layout and the controls available in
each section:

![General settings](assets/settings-general-full.png)

![General settings compact view](assets/settings-general.png)

![Provider status settings](assets/settings-providers.png)

![Notification settings](assets/settings-notifications.png)

![Sound settings](assets/settings-sounds.png)

## Runtime configuration

The daemon configuration has these main sections:

```json
{
  "providerMode": "auto",
  "providers": {"codex": {"enabled": true}},
  "monitoring": {"refreshInterval": 2},
  "notifications": {
    "enabled": true,
    "events": {"waiting": true, "completed": true, "error": true, "rateLimited": true}
  }
}
```

`auto` monitors detected providers, `manual` selects one provider and `multi` enables the configured
provider set. The extension can hide disconnected providers without disabling their detection. A
provider only contributes usage when the source is authenticated and the response is verifiable;
otherwise the UI keeps the provider status but displays `Consumption: Unavailable`.

## Notification sound settings

The Sounds tab provides independent custom sounds for Waiting, Completed, Error and Rate
limited events. An empty selection uses the system sound.

Supported formats:
MP3, OGG, OGA, WAV and FLAC

Maximum duration:
10 seconds

Maximum size:
5 MB

Files are checked by extension, MIME type, magic bytes, size, duration and actual decoder
availability. A valid MP3 with an unavailable runtime decoder is reported separately from a corrupt
file. Files that are removed after configuration are rejected at playback time and use the system
fallback.
