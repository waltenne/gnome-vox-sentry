# GNOME extension

The extension targets GNOME Shell 46 and uses GJS, St, PanelMenu, PopupMenu and Gio D-Bus APIs.
It renders a compact single-dot indicator and a native popup. Color mappings follow normalized states.
The preferences window uses a native Adwaita sidebar with General, Providers, Notifications, Sounds
and About pages. General includes the `Show only connected providers` option, enabled by default. When it is
disabled, the popup shows every supported provider with its current state; when enabled, offline
providers stay hidden. Each row includes a standard GNOME symbolic development icon, and clicking it
opens its sessions and consumption details; no third-party provider artwork is bundled. When enabled in
Preferences, the popup also shows aggregate token usage, limit windows and reset times provided by
the daemon. The usage section displays `Unavailable` when a provider does not expose those values.
The panel indicator uses one status dot, with a unique semantic color for every normalized state:

| Status | Color |
| --- | --- |
| `OFFLINE` | Gray (`#7a7a7a`) |
| `IDLE` | Green (`#2fb344`) |
| `THINKING` | Purple (`#a855f7`) |
| `WORKING` | Blue (`#3b82f6`) |
| `WAITING` | Yellow (`#facc15`) |
| `COMPLETED` | Bright green (`#22c55e`) |
| `ERROR` | Red (`#ef4444`) |
| `RATE_LIMITED` | Orange (`#f97316`) |
| `UNKNOWN` | Blue-gray (`#94a3b8`) |

The semantic class is selected from the normalized status, with invalid/future values falling back
to `UNKNOWN`. Provider text and status icons use the same palette. Colors are not applied to popup
containers or row backgrounds, and every state keeps its text label for accessibility. Notifications
use GNOME MessageTray, respect the Notifications preference and identify the provider whose state
changed. Returning from working/thinking to idle and entering a rate limit generate provider-specific
notifications.

The Preferences status test previews all nine states and can temporarily apply one to the panel dot
for five seconds before restoring the real status.

## Runtime screenshots

![Ready indicator](assets/indicator-ready.png)

![Provider and usage popup](assets/indicator-popup-usage.png)
