# Configuration

The GNOME preferences window is divided into five tabs:

- **Behavior**: provider mode, connected-provider filtering and session display.
- **Notifications**: desktop notifications, sounds and custom event audio.
- **Providers**: every supported provider with its live connection and status.
- **Usage**: token totals, quota windows and reset times.
- **Monitoring**: automatic refresh interval.

The **Show only connected providers** option is enabled by default. Disable it to keep offline
providers visible in the indicator and compare their status. The Providers tab always lists all
providers, including offline ones, so detection can be diagnosed without changing the dropdown.

## Configuration categories

| Tab | Configuration | Default |
| --- | --- | --- |
| Behavior | Provider mode (`Auto`, `Manual` or `Multi`), connected-only providers and multiple sessions | Auto, connected-only on, multiple sessions on |
| Notifications | Desktop notifications, sound playback, event sounds and notification simulation | Notifications and sounds on; all events on |
| Providers | Live connection, detected version and current status for every supported provider | Read-only diagnostics |
| Usage | Token totals, quota windows and reset times in provider dropdowns | Usage and limits on |
| Monitoring | Automatic status refresh interval | 2 seconds |

The Preferences window is opened from the indicator's **Settings** item. It uses GSettings with the
schema `org.gnome.shell.extensions.vox-sentry`. The daemon uses a separate JSON configuration file
at `$XDG_CONFIG_HOME/gnome-vox-sentry/config.json`, so provider enablement and daemon scheduling do
not depend on the Preferences process.

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

The Notifications tab provides independent custom sounds for Waiting, Completed, Error and Rate
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
