# EGO pre-submission checklist

Audit date: 2026-08-30. Target: GNOME Shell 46.

This audit follows the current [GNOME Shell Extensions Review Guidelines](https://gjs.guide/extensions/review-guidelines/review-guidelines.html),
[GNOME Extension Best Practices](https://gjs.guide/extensions/review-guidelines/best-practices.html),
the [GJS Preferences guide](https://gjs.guide/extensions/development/preferences.html), and the
current public EGO review record. Recent reviews continue to flag timeout cleanup, unnecessary
session modes, forbidden imports, `run_dispose()` and missing repository URLs; see, for example,
[Aurora Shell review 74360](https://extensions.gnome.org/review/74360),
[Avatar review 64661](https://extensions.gnome.org/review/64661), and
[removed review 64240](https://extensions.gnome.org/review/64240).

## Requirement matrix

| Requirement | Status | Evidence | Action |
|---|---|---|---|
| Metadata is minimal and valid | PASS | `gnome-extension/metadata.json:1-8`; UUID, URL and Shell 46 are present; deprecated `version` is absent | Keep UUID stable after publication |
| Schema namespace/path/filename | PASS | `gnome-extension/schemas/org.gnome.shell.extensions.vox-sentry.gschema.xml:2` | Keep XML in the ZIP; compile locally during installation |
| Declared GNOME versions are tested honestly | NEEDS REVIEW | `metadata.json` declares only `46`; this host is GNOME Shell 46.0 | Re-run after a fresh session; do not add other versions without testing |
| Objects are created after `enable()` | PASS | `extension.js:369-376`; runtime objects are constructed by `AgentIndicator` from `enable()` | Keep module scope limited to constants/classes |
| Indicator cleanup | PASS | `extension.js:334-366`; `destroy()` removes source, cancels calls, disconnects signals and destroys the indicator | Repeat in a fresh Shell session |
| D-Bus signal cleanup | PASS | `extension.js:72-79,342-346`; IDs are stored and disconnected | Exercise daemon restart and disable/re-enable |
| GLib timeout cleanup | PASS | `extension.js:82-86,335-338`; `prefs.js:97-106` | Stored IDs are removed on cleanup/close |
| Async callback safety | PASS | `extension.js:93-107,110-134`; cancellables and identity checks prevent stale updates | Keep callbacks bounded and cancellable |
| GObject disposal API | PASS | No `run_dispose()` in the extension package | None |
| Shell/prefs process isolation | PASS | `extension.js` imports Shell/St; `prefs.js` imports GTK/Adwaita; `soundManager.js` imports no UI library | None |
| Optional compatibility branches | PASS | No optional chaining or multi-version compatibility path in submitted GJS | Target Shell 46 only |
| Filesystem access | NEEDS REVIEW | `soundManager.js:98-135,188-193`; only user-selected/system audio is read | Full decoder probing is synchronous; see H-2 |
| Subprocesses in ZIP | PASS | No `Gio.Subprocess`, `GLib.spawn` or shell command in `gnome-extension/` | Provider subprocesses remain daemon-side |
| Shell injection | PASS | Audio is passed to GStreamer as a `file://` URI; no shell interpolation or player command exists | Re-test hostile filenames in Preferences |
| Network/telemetry/clipboard | PASS | Static search found none in the package | None |
| Privacy/logging | PASS | Extension logs only bounded connection, decode and notification errors; provider payloads stay daemon-side | Recheck release logs for secrets |
| GSettings migration | NEEDS REVIEW | Schema ID changed from the pre-publication `io.github...` ID to the EGO namespace | Publication is pre-release; document that old local settings are reset |
| D-Bus dependency unavailable | PASS | `extension.js:87-90,93-107`; offline state is rendered and polling is bounded | Document daemon prerequisite to EGO users |
| D-Bus identity is intentional | PASS | `extension.js:11-13` and `prefs.js:15-17` use the same local bus/path/interface | Keep this application identity stable |
| Notifications are transition-based | PASS | `extension.js:204-232`; previous/current provider states suppress repeats | Validate transitions in a fresh session |
| Audio validation | PASS | `soundManager.js:98-153`; MIME, header, size, duration and GStreamer decoder checks | Run decoder-unavailable fixture on a second environment |
| Styling is scoped | PASS | `stylesheet.css`; selectors use Vox Sentry classes and no `!important` | None |
| Accessibility/color independence | NEEDS REVIEW | Text labels accompany status colors; lamps are visual status reinforcement | Verify keyboard navigation/high contrast manually |
| Translation readiness | NEEDS REVIEW | No gettext domain/catalog; UI literals are English | Add translations before broad localization claims |
| Continuous resource usage | NEEDS REVIEW | Shell polls D-Bus every 5 seconds; provider-heavy scanning is daemon-side | Measure idle CPU/wakeups in a clean session |
| AI-assisted source readability | PASS | Four readable, non-minified modules; no prompt-like comments or imaginary API paths | Maintainer must understand and maintain submitted code |
| License compatibility | PASS | Repository `LICENSE` is GNU GPL-2.0-or-later | Preserve license notices when publishing |
| Public source repository | FAIL | Metadata URL is present, but inspected GitHub repository is incomplete | Resolve B-2 before EGO upload |
| Package contains only required files | PASS | `pack-ego.sh`; ZIP allowlist below; no tests/docs/daemon/assets | Recheck every release candidate |

## Extension signal inventory

| File/line | Owner and signal | Created in | Cleanup | Status |
|---|---|---|---|---|
| `extension.js:25-27` | `Gio.Settings::changed` | `AgentIndicator._init()` during `enable()` | `extension.js:347-349` | PASS |
| `extension.js:56` | Refresh menu `activate` | `AgentIndicator._init()` | Button owned by indicator; destroyed with it | PASS |
| `extension.js:65` | Settings menu `activate` | `AgentIndicator._init()` | Menu/indicator destruction | PASS |
| `extension.js:67-69` | Popup `open-state-changed` | `AgentIndicator._init()` | `extension.js:342-345` | PASS |
| `extension.js:72-75` | D-Bus `g-signal` | `AgentIndicator._init()` | `extension.js:339-341` | PASS |
| `extension.js:78` | D-Bus `notify::g-name-owner` | `AgentIndicator._init()` | `extension.js:339-341` | PASS |
| `soundManager.js:257-260` | GStreamer bus `message` | `play()` | Removed with bus watch in `stop()` | PASS |
| `prefs.js:126,132,349,357` | GSettings/UI notify signals | `fillPreferencesWindow()` | Window and widgets are closed/destroyed by Preferences | NEEDS REVIEW |
| `prefs.js:101` | Window `close-request` | `fillPreferencesWindow()` | Removes timer and nulls long-lived refs at `prefs.js:102-113` | PASS |

## GLib source inventory

| File/line | Source | ID stored | Cleanup | Status |
|---|---|---|---|---|
| `extension.js:82` | daemon retry/status polling | `_refreshSource` | `extension.js:335-338` | PASS |
| `prefs.js:97` | provider diagnostics polling | `_statusSource` | `prefs.js:102-105` | PASS |

## Version matrix

| GNOME Shell | Declared | Tested in this audit | Result |
|---|---:|---:|---|
| 46.0 | Yes | Static/runtime host checks; fresh logout/login pending | NEEDS REVIEW |
| Other versions | No | No | Not applicable |

## EGO package allowlist

Generated by `./pack-ego.sh` using `gnome-extensions pack`:

```text
metadata.json
LICENSE
extension.js
prefs.js
notificationManager.js
soundManager.js
stylesheet.css
schemas/org.gnome.shell.extensions.vox-sentry.gschema.xml
```

The daemon, providers, CLI, systemd unit, tests, documentation, development script and generated
schema cache are outside the ZIP. The project license is included in the ZIP for direct
distribution traceability. The external daemon boundary is documented in
`docs/architecture.md` and `docs/gnome/ego-blockers.md`.

## Final submission checklist

- [ ] Public repository contains the exact source and release history.
- [x] `metadata.json` contains the repository URL and stable UUID.
- [x] Shell version range is conservative (`46` only).
- [x] Lifecycle, signals, timers, D-Bus cancellation and audio stop paths are implemented.
- [ ] Shell-blocking audio validation is moved out of the Shell process or cached safely.
- [x] No unnecessary files, binaries, source maps or minified code are in the ZIP.
- [x] No secrets, telemetry, network or clipboard access is in the extension package.
- [x] License is GNU GPL-2.0-or-later and confirmed by the maintainer.
- [x] Custom audio validation and system fallback are implemented.
- [x] Package generated with GNOME tooling and inspected.
- [ ] Fresh-session enable/disable/re-enable and Preferences tests completed after logout/login.
- [x] EGO blocker report and changelog are updated.
