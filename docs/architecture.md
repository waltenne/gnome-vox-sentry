# Architecture

## Table of contents

- [Runtime flow](#runtime-flow)
- [Responsibilities and boundaries](#responsibilities-and-boundaries)
- [Compatibility](#compatibility)

```text
Provider -> Vox Sentry Core -> vox-sentryd -> D-Bus -> GNOME Extension
                                                    -> NotificationManager
                                                        -> SoundManager -> GStreamer
```

Core owns normalized models and aggregation. Providers own all discovery and translation logic. The
daemon schedules refreshes, isolates provider failures and publishes protocol v1 JSON. The extension
has no Codex knowledge: it consumes `GetStatus` and `StatusChanged`.

## Runtime flow

1. Provider adapters inspect local process/session metadata and, where supported, authenticated usage
   sources.
2. Core converts provider-specific observations into `AgentSession`, `AgentStatus` and `AgentUsage`
   models and aggregates the provider state.
3. `vox-sentryd` performs adaptive refreshes, keeps provider failures isolated and exposes the latest
   snapshot over the user session D-Bus.
4. The GNOME extension renders the snapshot as one semantic status dot and expandable provider dropdowns. It
   polls with cancellable calls and listens for status signals.
5. Normalized transition events reach `NotificationManager`; selected sounds are validated and sent
   to `SoundManager`/GStreamer for playback.

The extension is intentionally a thin client. The Python daemon is installed separately and the
extension remains safe when the daemon is stopped: it shows the local monitor as offline and does
not start provider processes itself.

## Responsibilities and boundaries

Core owns normalized models and aggregation. Providers own discovery and translation. The daemon
owns scheduling, failure isolation and the D-Bus service. The extension owns presentation and user
preferences; `NotificationManager` owns desktop notifications and `SoundManager` owns audio
validation and playback.

The implementation is Python 3.10+ for Core/daemon/CLI and GJS for GNOME Shell 46. Gio/GLib is
used for the session-bus service because it is part of a GNOME desktop. NotificationManager owns
visual GNOME MessageTray delivery; SoundManager owns sound validation and playback. Both use the
same normalized event type, and sound validation requires extension/MIME/header agreement, valid
duration and size, and a working GStreamer decoder. MP3 follows exactly the same path and limits as
OGG, OGA, WAV and FLAC.

The package metadata declares only GNOME Shell 46. Other GNOME Shell versions are not claimed until
they have been tested and added deliberately to `gnome-extension/metadata.json`.

## Compatibility

The implementation requires Python 3.10+ for Core/daemon/CLI and GNOME Shell 46 for the GJS
client. The EGO package contains only the extension runtime; the daemon remains a separate local
installation requirement.
