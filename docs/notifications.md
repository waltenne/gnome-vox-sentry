# Notifications and notification sounds

Vox Sentry sends provider-specific GNOME notifications for waiting, completed, error and
rate-limited transitions. Desktop notifications and sounds can be enabled independently in the
**Notifications** preferences tab.

## Supported audio

Custom event sounds are validated by content and by the GStreamer runtime before they are saved or
played. The file extension alone is never trusted. The extension must be compatible with its
detected MIME type and magic header, have a valid decoded stream and satisfy the common limits.

Supported formats:
MP3, OGG, OGA, WAV and FLAC

Maximum duration:
10 seconds

Maximum size:
5 MB

MP3 is a normal supported format, not an experimental path. GStreamer must have an MP3 parser and
decoder available at runtime. If a selected MP3 is valid but its decoder is unavailable, Vox Sentry
reports:

```text
Unable to play MP3 file

Vox Sentry could not decode the selected MP3 audio.

Verify that the required multimedia codecs are available on your system.
```

If a configured custom file is removed or becomes corrupt, Vox Sentry falls back to the matching
system alert sound. A missing or corrupt custom file never prevents the visual notification from
being delivered.

When no custom file is selected, each event uses a distinct sound from the standard GNOME alert
theme when available: Waiting prefers `string` (Text), Completed prefers `click`, Error prefers
`swing`, and Rate limited prefers `hum`. Freedesktop event sounds such as `message-new-instant`,
`dialog-error`, `alarm-clock-elapsed` and `bell` are ordered fallbacks when the GNOME alert theme
is unavailable.

## Playback path

```text
Provider -> Core -> normalized status transition -> NotificationManager
    -> SoundManager -> MIME/header/size/duration/decode validation
    -> GStreamer decoder/backend -> playback
```

The **Preview** button uses the same validation and playback path as real event notifications.
