# GNOME extension

The extension targets GNOME Shell 46 and uses GJS, St, PanelMenu, PopupMenu and Gio D-Bus APIs.
It renders a compact three-lamp indicator and a native popup. Color mappings follow normalized states;
The preferences window is organized into Behavior, Notifications, Providers, Usage and Monitoring tabs. The
Behavior tab includes the `Show only connected providers` option, enabled by default. When it is
disabled, the popup shows every supported provider with its current state; when enabled, offline
providers stay hidden. Each row includes a standard GNOME symbolic development icon, and clicking it
opens its sessions and consumption details; no third-party provider artwork is bundled. When enabled in
Preferences, the popup also shows aggregate token usage, limit windows and reset times provided by
the daemon. The usage section displays `Unavailable` when a provider does not expose those values.
The panel indicator is a three-lamp
traffic light: green means ready/idle, amber means processing or waiting and red means
offline, error or rate-limited. Notifications use GNOME MessageTray, respect the Notifications
preference and identify the provider whose state changed. Returning from working/thinking to idle
and entering a rate limit generate provider-specific notifications.
