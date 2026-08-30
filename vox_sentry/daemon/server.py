"""Lightweight GLib/D-Bus daemon exposing protocol v1 JSON strings."""

from __future__ import annotations

import argparse
import json
import logging
import signal

from ..builtins import default_registry
from ..config import load_config
from ..core import VoxSentryCore
from ..protocol import snapshot_to_json

LOG = logging.getLogger("vox-sentryd")
BUS_NAME = "io.github.gnome_vox_sentry"
OBJECT_PATH = "/io/github/gnome_vox_sentry"
INTERFACE = "io.github.gnome_vox_sentry"
INTROSPECTION = f'''<node><interface name="{INTERFACE}">
<method name="GetStatus"><arg direction="out" type="s"/></method>
<method name="GetProviders"><arg direction="out" type="s"/></method>
<method name="GetSessions"><arg direction="out" type="s"/></method>
<method name="GetUsage"><arg direction="out" type="s"/></method>
<method name="Reload"><arg direction="out" type="s"/></method>
<method name="TestNotification"><arg direction="in" type="s"/><arg direction="out" type="s"/></method>
<signal name="StatusChanged"><arg type="s"/></signal>
<signal name="NotificationTest"><arg type="s"/></signal>
<signal name="SessionStarted"><arg type="s"/></signal><signal name="SessionChanged"><arg type="s"/></signal>
<signal name="SessionEnded"><arg type="s"/></signal><signal name="UsageChanged"><arg type="s"/></signal>
<signal name="ProviderDetected"><arg type="s"/></signal><signal name="ProviderUnavailable"><arg type="s"/></signal>
</interface></node>'''


class DbusService:
    def __init__(self, core: VoxSentryCore) -> None:
        try:
            import gi
            gi.require_version("Gio", "2.0")
            from gi.repository import Gio, GLib
        except ImportError as exc: raise RuntimeError("PyGObject Gio/GLib is required for vox-sentryd") from exc
        self.Gio, self.GLib, self.core = Gio, GLib, core
        self.loop, self.connection = GLib.MainLoop(), None
        self.name_lost = False
        self.interface_info = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION).interfaces[0]
        self.core.add_listener(self._event)

    def start(self) -> None:
        self.Gio.bus_own_name(self.Gio.BusType.SESSION, BUS_NAME, self.Gio.BusNameOwnerFlags.NONE, self._bus_acquired, None, self._name_lost)
        interval = max(1, int(self.core.config.get("monitoring", {}).get("refreshInterval", 2)))
        self.core.refresh(); self.GLib.timeout_add_seconds(interval, self._tick); self.loop.run()

    def _bus_acquired(self, connection, _name) -> None:
        self.connection = connection
        connection.register_object(OBJECT_PATH, self.interface_info, self._method_call, None, None)

    def _name_lost(self, _connection, _name) -> None:
        self.name_lost = True
        LOG.error("could not acquire D-Bus name %s", BUS_NAME)
        self.loop.quit()

    def _method_call(self, _connection, _sender, _path, _interface, method, _params, invocation) -> None:
        try:
            if method == "TestNotification":
                event_type = _params.unpack()[0].upper()
                if event_type not in {"WAITING", "COMPLETED", "ERROR", "RATE_LIMITED"}:
                    invocation.return_dbus_error(f"{INTERFACE}.Error", "Unknown notification event")
                    return
                self._signal("NotificationTest", event_type)
                invocation.return_value(self.GLib.Variant("(s)", (event_type,)))
                return
            snapshot = self.core.reload() if method == "Reload" else self.core.get_status()
            if method == "GetProviders": value = json.dumps([p.to_dict() for p in snapshot.providers])
            elif method == "GetSessions": value = json.dumps([s.to_dict() for s in snapshot.sessions])
            elif method == "GetUsage": value = json.dumps({k: v.to_dict() for k, v in snapshot.usage.items()})
            elif method in {"GetStatus", "Reload"}: value = snapshot_to_json(snapshot)
            else:
                invocation.return_dbus_error(f"{INTERFACE}.Error", "Unknown method"); return
            invocation.return_value(self.GLib.Variant("(s)", (value,)))
        except Exception as exc:
            LOG.exception("D-Bus call failed"); invocation.return_dbus_error(f"{INTERFACE}.Error", str(exc))

    def _tick(self) -> bool:
        before = self.core.get_status().to_dict(); after = self.core.refresh()
        before.pop("generatedAt", None); current = after.to_dict(); current.pop("generatedAt", None)
        if self.connection and before != current: self._signal("StatusChanged", snapshot_to_json(after))
        return True

    def _signal(self, name: str, value: str) -> None:
        if self.connection:
            self.connection.emit_signal(None, OBJECT_PATH, INTERFACE, name, self.GLib.Variant("(s)", (value,)))

    def _event(self, event) -> None:
        mapping = {"status.changed": "StatusChanged", "session.started": "SessionStarted", "session.ended": "SessionEnded", "provider.error": "ProviderUnavailable"}
        signal_name = mapping.get(event.type)
        if signal_name: self._signal(signal_name, json.dumps(event.to_dict(), separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vox-sentryd")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--log-level", default="WARNING", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(name)s: %(message)s")
    core = VoxSentryCore(default_registry(), load_config())
    if args.once: print(snapshot_to_json(core.refresh())); return 0
    service = DbusService(core)
    signal.signal(signal.SIGTERM, lambda *_: service.loop.quit()); signal.signal(signal.SIGINT, lambda *_: service.loop.quit())
    service.start()
    # Let systemd's Restart=on-failure recover from a transient D-Bus name
    # collision or a session-bus reconnect. A normal SIGTERM/SIGINT remains 0.
    return 1 if service.name_lost else 0
