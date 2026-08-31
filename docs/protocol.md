# Protocol v1

Every snapshot contains `protocolVersion: 1`, normalized `status`, provider descriptors, sessions,
usage and `generatedAt`. D-Bus methods return JSON strings so clients can evolve independently.

Methods on `io.github.gnome_vox_sentry` at `/io/github/gnome_vox_sentry`:

- `GetStatus() -> string`
- `GetProviders() -> string`
- `GetSessions() -> string`
- `GetUsage() -> string`
- `Reload() -> string`

- `TestNotification(eventType) -> string`

Signals carry one JSON string: `StatusChanged`, `SessionStarted`, `SessionChanged`, `SessionEnded`,
`UsageChanged`, `ProviderDetected`, and `ProviderUnavailable`.

`TestNotification` is a local diagnostic method used by Preferences to exercise the real GNOME
notification and sound path through the enabled extension.
