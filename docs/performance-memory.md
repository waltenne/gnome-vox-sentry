# Memory usage audit

This audit separates Vox Sentry's memory from GNOME Shell, provider processes and the Codex
app-server. Measurements were taken on GNOME 46, Linux x86-64, with the development extension
installed from the generated EGO package. Values below are observations, not universal budgets.

## Measurement method

For each process, RSS and VSZ came from `ps`. PSS, private resident memory (USS approximation) and
anonymous memory came from `/proc/<pid>/smaps_rollup`:

```text
RSS = resident pages attributed to the process
PSS = resident pages weighted by sharing
USS = Private_Clean + Private_Dirty
VSZ = virtual address space; it is not RAM usage
```

`smem` and Sysprof were not installed in this environment, so PSS/USS were collected directly from
the kernel's `smaps_rollup`. A short-lived GJS audio harness used `/usr/bin/time` for peak RSS.

## Baseline ownership

The initial screenshot-like value was the daemon's approximately 330 MB VSZ, not its resident
memory. The same measurement found a large GNOME Shell and Codex app-server footprint:

| Process | RSS | PSS | USS | VSZ | Interpretation |
|---|---:|---:|---:|---:|---|
| `vox-sentryd` | 27.7 MB | 16.4 MB | 13.8 MB | 331.0 MB | Vox Sentry daemon |
| `gnome-shell` | 305.7 MB | 198.5 MB | 180.2 MB | 5.9 GB | Shell plus all enabled extensions/theme |
| Codex `app-server` | 196.8 MB | 196.8 MB | 196.8 MB | 692.6 MB | Provider-owned child process |
| Codex code-mode host | 21.5 MB | 21.5 MB | 21.5 MB | 1.35 TB | Provider/VS Code helper |

GNOME Shell with Vox Sentry enabled measured 305.8 MB RSS / 198.6 MB PSS / 180.3 MB USS. With the
extension disabled it measured 305.5 MB RSS / 198.4 MB PSS / 180.1 MB USS. Re-enabling measured
306.3 MB RSS / 199.1 MB PSS / 180.8 MB USS. This is an approximately 0.8 MB warm incremental
observation, within normal Shell allocation and fragmentation noise; the ~300 MB process is not
owned by Vox Sentry alone.

## Changes applied

- Popup rows are no longer reconstructed when the normalized snapshot and relevant settings are
  unchanged. A compact menu key prevents repeated `removeAll()` and widget allocation on close/open
  cycles.
- Preferences clears provider and sound row maps, settings and proxy references on close.
- Notification objects are transient, preventing repeated status notifications from accumulating in
  GNOME's persistent notification history.
- Validated sound metadata remains cached, but the cache is capped at 32 paths and evicted FIFO-style.
  The default system-sound cache remains limited to the four event types and a 60-second TTL.
- Sound cache timestamp reads use a type-safe GIO accessor, eliminating repeated `GLib-GIO-CRITICAL`
  messages during preview.
- Daemon shutdown removes its active GLib source and marks the scheduler stopped. The user unit has
  a 15-second stop bound so an in-flight provider check cannot leave systemd waiting indefinitely.

No unbounded event queue, notification history, provider history or snapshot history was found.
The daemon retains only the current normalized snapshot, current sessions and current usage map.
Provider process/log/database reads are bounded to current process metadata, recent file tails or a
single database row.

## Stress results

| Scenario | Result |
|---|---|
| 20 extension disable/enable cycles | Passed; Shell RSS briefly rose to 308.9 MB and returned to ~306.6–306.8 MB after settling |
| 20 daemon restarts with cooldown | Passed; all active, `NRestarts=0` |
| 50 manual refreshes | Passed |
| 50 notifications across WAITING/COMPLETED/ERROR/RATE_LIMITED | Passed; daemon RSS remained ~27.5–27.8 MB; Shell settled near baseline |
| 50 MP3 previews | Passed; no GIO warnings after the timestamp fix; GJS peak RSS 39.1 MB |
| 1/2/4/8 mock providers | Passed; traced refresh allocation grew from 2 KB to 10 KB |
| 1/10/50/100 mock sessions | Passed; traced refresh allocation grew from 1 KB to 46 KB; no history retained |
| 60 real refreshes in one daemon-equivalent process | Passed; RSS rose from 17.0 MB to 18.6 MB and then plateaued |

The 30-minute monitor recorded Shell RSS/PSS/USS of 298–313/194–206/176–189 MB and daemon
RSS/PSS/USS of 17.0–29.9/11.5–18.8/9.3–16.2 MB. The lowest daemon sample coincided with the
deliberate restart stress, and the monitor also overlapped extension installation and desktop
activity; it is therefore a system observation, not a clean leak-proof benchmark. The direct
60-refresh process-equivalent run plateaued at 18.6 MB RSS. Popup and Preferences open/close loops
require interactive GNOME input and remain manual validation items; lifecycle cleanup is covered
by the source audit and extension reload test.

## Current assessment

**MEMORY READINESS: PASS WITH WARNINGS**

The daemon has a low stable private baseline and bounded state. The high system-level numbers are
primarily GNOME Shell and the Codex app-server, so they should not be used as a Vox Sentry daemon
budget. The remaining warning is that Shell-wide memory includes unrelated extensions and the
custom desktop theme; an isolated Shell/Sysprof run is required for a definitive extension-only
allocation profile.
