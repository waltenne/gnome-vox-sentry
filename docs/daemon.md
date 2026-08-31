# Daemon

`vox-sentryd` refreshes enabled providers every two seconds by default, keeps normalized state in
memory and exposes one user-session D-Bus name. It can run as a systemd user service. Provider
failures are logged and isolated; the daemon continues monitoring other providers.

The user service does not enable `PrivateTmp`: provider detection needs to inspect readable
`/proc/<pid>/fd` links for active rollout and log files. The daemon only reads metadata and tails
bounded files; it does not write temporary data there.

The process observer uses one short-lived shared `/proc` snapshot per refresh cycle. Providers reuse
that snapshot for detection, sessions and status instead of rescanning the process table for each
operation. Notification sound discovery and successful custom-file validation are cached in the
GNOME client; file size and modification time are checked before a cached validation is reused.
