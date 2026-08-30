# Changelog

## Unreleased

- Added official MP3 notification sound support alongside OGG, OGA, WAV and FLAC.
- Added content/MIME/header/integrity/decoder validation with shared 10-second and 5 MB limits.
- Added custom sound preview, per-event sounds, system fallback and explicit MP3 codec diagnostics.
- Added categorized GNOME Preferences tabs and live provider status diagnostics.
- Added GNOME 46 lifecycle cleanup, cancellable Shell D-Bus calls and a reproducible EGO package
  allowlist via `pack-ego.sh`.
- Corrected the GNOME settings schema namespace and made notifications use the system MessageTray
  source to avoid stale disposed-source errors.
- Simplified the GNOME 46 submission path by removing compatibility optional checks and moving
  GStreamer initialization into the runtime sound manager.
- Relicensed the project under GNU GPL-2.0-or-later for GNOME Shell extension distribution.

## 0.1.0 - 2026-08-30

- Initial local-first Core, provider registry, session model and protocol v1.
- Working process/metadata Codex provider with conservative capability reporting.
- Mock providers, daemon, D-Bus API, CLI and GNOME Shell extension skeleton.
- XDG configuration, systemd user unit and contributor documentation.
