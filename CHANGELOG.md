# Changelog

## Unreleased

Changes not yet included in a tagged release.

## 0.1.0 - 2026-08-31

- Replaced the grouped red/amber/green indicator with one compact semantic status dot and a unique
  color class for every normalized state; provider labels and icons now use the same palette.
- Added a shared status presentation map, a color preview for every state in Preferences and a
  five-second panel status test with automatic restoration.
- Added official MP3 notification sound support alongside OGG, OGA, WAV and FLAC.
- Added content/MIME/header/integrity/decoder validation with shared 10-second and 5 MB limits.
- Added custom sound preview, per-event sounds, system fallback and explicit MP3 codec diagnostics.
- Added categorized GNOME Preferences tabs and live provider status diagnostics.
- Added GNOME 46 lifecycle cleanup, cancellable Shell D-Bus calls and a reproducible EGO package
  allowlist via `pack-ego.sh`.
- Reduced daemon refresh overhead by sharing a short-lived `/proc` snapshot across providers and
  avoiding duplicate session scans; cached notification sound discovery and validation in the
  extension client.
- Added adaptive daemon refresh cadence, dirty-snapshot UI updates, performance measurements and
  contributor/security/release project guidance.
- Reduced repeated popup allocations with snapshot/settings-aware menu reuse, bounded sound
  validation metadata, transient notifications and explicit Preferences cleanup.
- Hardened daemon shutdown and documented RSS/PSS/USS memory ownership and stress measurements in
  `docs/performance-memory.md`.
- Fixed Claude idle detection by parsing top-level session events instead of matching text inside
  historical prompts and tool results.
- Debounced Ready notifications and suppressed them while a provider still exposes an active
  working session, preventing transient Codex item transitions from announcing completion early.
- Fixed systemd sandboxing that hid provider rollout descriptors and caused multi-chat Codex status
  detection to fall back to a single chat.
- Corrected the GNOME settings schema namespace and made notifications use the system MessageTray
  source to avoid stale disposed-source errors.
- Simplified the GNOME 46 submission path by removing compatibility optional checks and moving
  GStreamer initialization into the runtime sound manager.
- Relicensed the project under GNU GPL-2.0-or-later for GNOME Shell extension distribution.

- Initial local-first Core, provider registry, session model and protocol v1.
- Working process/metadata Codex provider with conservative capability reporting.
- Mock providers, daemon, D-Bus API, CLI and GNOME Shell extension skeleton.
- XDG configuration, systemd user unit and contributor documentation.
