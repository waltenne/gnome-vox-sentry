import json

from vox_sentry.models import AgentStatus, Snapshot
from vox_sentry.protocol import snapshot_to_json


def test_protocol_is_versioned_and_json_safe():
    payload = json.loads(snapshot_to_json(Snapshot(1, AgentStatus.OFFLINE, [], [])))
    assert payload["protocolVersion"] == 1 and payload["status"] == "OFFLINE"
