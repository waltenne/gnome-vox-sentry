"""vox-sentry CLI client, with a direct Core fallback when the daemon is not running."""

from __future__ import annotations

import argparse
import json

from .builtins import default_registry
from .config import load_config, save_config
from .core import VoxSentryCore
from .protocol import pretty_json

BUS_NAME = "io.github.gnome_vox_sentry"
OBJECT_PATH = "/io/github/gnome_vox_sentry"
INTERFACE = "io.github.gnome_vox_sentry"


def _dbus_snapshot() -> dict | None:
    try:
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio
        proxy = Gio.DBusProxy.new_for_bus_sync(Gio.BusType.SESSION, Gio.DBusProxyFlags.NONE, None, BUS_NAME, OBJECT_PATH, INTERFACE, None)
        result = proxy.call_sync("GetStatus", None, Gio.DBusCallFlags.NONE, 1500, None)
        return json.loads(result.unpack()[0])
    except Exception:  # noqa: BLE001 - D-Bus is optional; direct Core is the safe fallback.
        return None


def snapshot() -> dict:
    value = _dbus_snapshot()
    return value if value is not None else VoxSentryCore(default_registry(), load_config()).refresh().to_dict()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vox-sentry")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "sessions", "providers"):
        command = sub.add_parser(name); command.add_argument("--json", action="store_true")
    provider = sub.add_parser("provider"); provider.add_argument("action", choices=("use", "enable", "disable")); provider.add_argument("provider_id")
    args = parser.parse_args(argv)
    if args.command == "provider":
        config = load_config()
        if args.action == "use":
            if args.provider_id in ("auto", "multi"): config["providerMode"], config["provider"] = args.provider_id, None
            else: config["providerMode"], config["provider"] = "manual", args.provider_id
        else: config.setdefault("providers", {}).setdefault(args.provider_id, {})["enabled"] = args.action == "enable"
        print(f"Saved {save_config(config)}"); return 0
    value = snapshot()
    if args.json: print(pretty_json(value)); return 0
    if args.command == "providers":
        enabled = load_config().get("providers", {})
        print("PROVIDER     AVAILABLE     ENABLED     ACTIVE")
        for item in value.get("providers", []): print(f"{item['id']:<12}{'yes' if item['available'] else 'no':<14}{'yes' if enabled.get(item['id'], {}).get('enabled', False) else 'no':<12}{'yes' if item['active'] else 'no'}")
    elif args.command == "sessions":
        for item in value.get("sessions", []): print(f"{item['id']}\t{item['status']}\t{item.get('workspace') or '-'}")
    else:
        print("Vox Sentry\n\nStatus: " + value["status"].title() + f"\nSessions: {len(value.get('sessions', []))}")
        for item in value.get("sessions", []): print(f"  {item['provider']} · {item['status'].title()} · {item.get('workspace') or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
