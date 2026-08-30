import json
from typing import Any

from .models import Snapshot

PROTOCOL_VERSION = 1


def snapshot_to_dict(snapshot: Snapshot) -> dict[str, Any]:
    return snapshot.to_dict()


def snapshot_to_json(snapshot: Snapshot) -> str:
    return json.dumps(snapshot_to_dict(snapshot), ensure_ascii=False, separators=(",", ":"))


def pretty_json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)
