# Daemon

`vox-sentryd` refreshes enabled providers every two seconds by default, keeps normalized state in
memory and exposes one user-session D-Bus name. It can run as a systemd user service. Provider
failures are logged and isolated; the daemon continues monitoring other providers.
