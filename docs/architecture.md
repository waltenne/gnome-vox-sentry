# Architecture

```text
Provider -> Vox Sentry Core -> vox-sentryd -> D-Bus -> GNOME Extension
                                                    -> NotificationManager
                                                        -> SoundManager -> GStreamer
```

Core owns normalized models and aggregation. Providers own all discovery and translation logic. The
daemon schedules refreshes, isolates provider failures and publishes protocol v1 JSON. The extension
has no Codex knowledge: it consumes `GetStatus` and `StatusChanged`.

The implementation is Python 3.10+ for Core/daemon/CLI and GJS for GNOME Shell 46. Gio/GLib is
used for the session-bus service because it is part of a GNOME desktop. NotificationManager owns
visual GNOME MessageTray delivery; SoundManager owns sound validation and playback. Both use the
same normalized event type, and sound validation requires extension/MIME/header agreement, valid
duration and size, and a working GStreamer decoder. MP3 follows exactly the same path and limits as
OGG, OGA, WAV and FLAC.
