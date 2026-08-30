# EGO blockers and publication report

Audit date: 2026-08-30

Result: **NOT READY FOR EGO SUBMISSION**

This result reflects publication requirements, not only whether the extension runs locally.

## BLOCKER

### B-1 — The metadata URL does not currently expose the complete source

`metadata.json` points to `https://github.com/waltenne/gnome-vox-sentry`, but the inspected public
repository currently exposes only its license file, while this working tree has no `.git` metadata.
EGO reviewers must be able to inspect the exact source and license. Publish the complete source,
documentation and release history at that URL, or change the URL to the authoritative source before
submission. No commit SHA is available in this workspace.

## HIGH

### H-1 — The daemon is an external runtime prerequisite

The extension does not bundle or start `vox-sentryd`; it connects to the existing user-session D-Bus
service. This is the safer boundary for heavy provider discovery, and the GNOME guidance allows
separate processes for heavy work, but an EGO-only installation cannot provide the daemon. The
extension handles the missing service without crashing and displays Offline. The EGO listing and
README must clearly state the prerequisite and installation path, and maintainers should verify that
the extension remains useful and reviewable when the service is missing.

### H-2 — Full sound validation is synchronous in the Shell process

The sound manager performs file reads and GStreamer discovery synchronously before playback. This
is bounded and avoids accepting invalid files, but it can block the Shell main loop on slow storage
or codec probing. Before submission, move expensive validation to the preferences process or cache
validated file metadata, and keep the Shell playback path asynchronous/non-blocking. This is not
classified as a blocker because the feature is local and bounded, but it is a significant review
and UX risk.

## INFORMATIONAL

- The Python daemon and providers are not included in the EGO ZIP and use subprocesses outside the
  Shell process. They should remain separately documented and packaged.
- Provider-specific third-party artwork was removed from the extension package; the UI uses a
  standard GNOME symbolic development icon to avoid unverified trademark/license material.
- `gnome-extensions pack` does not include the generated `gschemas.compiled`; the ZIP contains the
  schema XML and GNOME 44+ can compile it during installation.
- `Refresh status` remains useful because it asks the daemon to perform an immediate provider
  refresh; automatic polling continues independently.

## Required evidence before submission

```text
./pack-ego.sh dist
unzip -t dist/vox-sentry@gnome-vox-sentry.shell-extension.zip
gnome-extensions install --force dist/vox-sentry@gnome-vox-sentry.shell-extension.zip
gnome-extensions enable vox-sentry@gnome-vox-sentry
systemctl --user status vox-sentryd
journalctl --user -u vox-sentryd --since today
journalctl -b /usr/bin/gnome-shell | rg 'Vox Sentry|Extension|JS ERROR'
```

The last two commands are environment checks, not substitutes for the source-publication blocker
above. The project is now licensed under GNU GPL-2.0-or-later, compatible with the terms required
for GNOME Shell extension distribution. A clean GNOME session or logout/login is required when the
Shell does not discover a newly installed user extension.
