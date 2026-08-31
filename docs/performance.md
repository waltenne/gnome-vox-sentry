# Performance report

This report records measurements from the GNOME 46 development environment used for Vox Sentry.
The numbers are observations, not an approval guarantee or a hard performance budget.

## Before and after

The baseline was measured before the shared process snapshot and duplicate-session optimizations.
The daemon was monitoring the same local process table in both runs.

| Measurement | Baseline | Optimized | Method |
|---|---:|---:|---|
| Core refresh, three cycles | 1.876 s | 0.247 s | Python `cProfile` around `VoxSentryCore.refresh()` |
| Process snapshots per refresh | about 10 | 1 | `cProfile` call count and `/proc` read profile |
| Daemon CPU, active Codex session | 17.8–17.9% | 2.2–2.4% | five `ps` samples at two-second intervals |
| Daemon RSS | 28.2 MB | 26.5–26.7 MB | `ps` resident memory samples |

The measured refresh cost fell by about 87%. RSS is the relevant resident-memory measure; the
larger VIRT value shown by `top` includes mapped address space and is not equivalent to allocated
RAM. The optimized daemon uses a shared process snapshot, passes collected sessions into status
calculation and refreshes more slowly when the aggregate state is idle or unavailable.

## Monitoring inventory

| Component | Purpose | Current cadence | Idle behavior | Owner |
|---|---|---:|---|---|
| `vox-sentryd` | Provider detection, sessions, status and usage | Adaptive: base interval while active, 10 s idle, 20 s unavailable | Slows down; one centralized scheduler | `DbusService` |
| Codex usage | Authenticated limits and token totals | 60 s cache | No account app-server request on every status cycle | `CodexProvider` |
| GNOME Shell D-Bus fallback | Recovery when a status signal is missed or daemon restarts | 5 s | Bounded fallback; normal changes arrive through `StatusChanged` | `extension.js` |
| Preferences diagnostics | Status shown while Preferences is open | Preferences window lifecycle | Timer is removed on close | `prefs.js` |
| Notification sounds | Validate/play only for a transition or explicit preview | Event-driven | No sound polling or file watching | `NotificationManager` / `SoundManager` |

The daemon is the only component that scans providers. The Shell extension receives normalized
snapshots and updates the indicator. Providers reuse one short-lived `/proc` snapshot per daemon
refresh, and provider-specific usage is cached independently from fast session state.

## Scenario coverage

| Scenario | Evidence | Result |
|---|---|---|
| No providers / unavailable daemon | Core fallback, D-Bus offline handling and adaptive scheduler code | No busy retry loop; unavailable cadence is 20 s |
| Codex installed and idle | Local provider status snapshot | Status remains observable; scheduler uses idle cadence |
| Codex working/waiting | Live daemon sample and provider tests | Base cadence is retained for responsiveness |
| Multiple sessions/providers | `tests/test_core.py`, provider tests | One shared process snapshot; sessions remain separate |
| Popup closed | Dirty-snapshot guard in `extension.js` | No UI rebuild when normalized data is unchanged |
| Popup open | Menu is retained while open and rebuilt on close | Avoids replacing visible rows during updates |
| Notification activity | Transition logic plus sound tests | Repeated identical states do not notify repeatedly |
| Preferences closed | `prefs.js` close cleanup and source inventory | Diagnostics timer is removed |

GNOME Shell CPU and wakeups were not isolated from the other desktop extensions in this session;
the extension-side design therefore uses structural safeguards (D-Bus signals, dirty snapshots,
bounded fallback polling and lifecycle cleanup) rather than claiming an absolute Shell CPU number.

## Performance contract for providers

New providers must use the Core scheduler and must not create independent background loops. A
provider should avoid repeated CLI version commands, whole-filesystem scans and process scans. Slow
usage/limit APIs belong behind a cache, and unavailable providers must not retry in a tight loop.
Heavy discovery remains daemon-side; the EGO ZIP contains only the thin GNOME client.
