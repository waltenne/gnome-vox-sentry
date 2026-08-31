from vox_sentry.daemon.server import DbusService
from vox_sentry.models import AgentStatus, Snapshot


def _service(base_interval: int = 2) -> DbusService:
    service = object.__new__(DbusService)
    service._base_interval = base_interval
    return service


def _snapshot(status: AgentStatus) -> Snapshot:
    return Snapshot(protocol_version=1, status=status, providers=[], sessions=[])


def test_adaptive_scheduler_keeps_active_sessions_responsive():
    service = _service(base_interval=3)

    assert service._next_interval(_snapshot(AgentStatus.WORKING)) == 3
    assert service._next_interval(_snapshot(AgentStatus.WAITING)) == 3


def test_adaptive_scheduler_slows_idle_and_unavailable_states():
    service = _service(base_interval=3)

    assert service._next_interval(_snapshot(AgentStatus.IDLE)) == 10
    assert service._next_interval(_snapshot(AgentStatus.COMPLETED)) == 10
    assert service._next_interval(_snapshot(AgentStatus.OFFLINE)) == 20
    assert service._next_interval(_snapshot(AgentStatus.UNKNOWN)) == 20
