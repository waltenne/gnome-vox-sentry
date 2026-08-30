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
