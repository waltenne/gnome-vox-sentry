# Vox Sentry documentation

This directory contains the technical, user-facing and publication documentation for Vox Sentry.
Start with the installation guide if you want to run the project, or the architecture guide if you
want to understand the implementation.

## Table of contents

- [Getting started](#getting-started)
- [User configuration](#user-configuration)
- [How it works](#how-it-works)
- [Providers](#providers)
- [Notifications and audio](#notifications-and-audio)
- [Development](#development)
- [Performance](#performance)
- [Release and GNOME publication](#release-and-gnome-publication)
- [Planning and compatibility](#planning-and-compatibility)

## Getting started

- [Installation guide](installation.md) — requirements, daemon setup, extension installation,
  package installation and troubleshooting.
- [Configuration](configuration.md) — Preferences categories, GSettings, daemon JSON and usage.

## User configuration

- [Configuration](configuration.md) — General, Providers, Notifications, Sounds and About pages.
- [Notifications and sounds](notifications.md) — notification events, system defaults, custom
  audio, MP3 diagnostics and common limits.
- [GNOME extension](gnome-extension.md) — panel indicator, semantic colors and lifecycle behavior.

## How it works

- [Architecture](architecture.md) — provider, Core, daemon, D-Bus and GNOME client flow.
- [Protocol v1](protocol.md) — D-Bus methods, signals and normalized payloads.
- [Daemon](daemon.md) — scheduling, service lifecycle and failure isolation.

## Providers

- [Provider overview](providers.md) — built-in providers and capability policy.
- [Codex provider](codex-provider.md) — local sessions, app-server usage and status detection.
- [Gemini and Antigravity](google-providers.md) — discovery and verified usage behavior.
- [Copilot, Claude Code and OpenCode](other-providers.md) — process and session discovery.
- [Creating a provider](creating-provider.md) — adapter contract and extension process.

## Notifications and audio

[Notifications and sounds](notifications.md) documents the complete path from a normalized event
to GStreamer playback. It also explains why extension, MIME type, magic bytes, integrity,
decodability, duration and size are all checked before a sound is accepted.

## Development

- [Development](development.md) — local environment, tests, linting and GNOME version policy.
- [Protocol v1](protocol.md) — contract for additional clients.
- [Creating a provider](creating-provider.md) — provider implementation guidance.

## Performance

- [Performance report](performance.md) — refresh strategy, provider inventory and CPU contract.
- [Memory usage audit](performance-memory.md) — ownership, RSS/PSS/USS measurements and stress
  results.

## Release and GNOME publication

- [Release guide](releasing.md) — semantic tags, GitHub Actions, EGO package and checksums.
- [EGO review checklist](gnome/ego-review-checklist.md) — pre-submission evidence and package
  allowlist.
- [EGO blockers](gnome/ego-blockers.md) — known publication constraints and mitigations.
- [Roadmap](roadmap.md) — completed milestone and next implementation phases.

## Planning and compatibility

- [GNOME compatibility](development.md#supported-gnome-version) — currently supported Shell
  version and the process for adding another one.
- [Project roadmap](roadmap.md) — future provider usage, adapter API and additional clients.
