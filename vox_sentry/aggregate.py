from .models import AgentSession, AgentStatus

STATUS_PRIORITY = {AgentStatus.ERROR: 0, AgentStatus.RATE_LIMITED: 1, AgentStatus.WAITING: 2, AgentStatus.WORKING: 3, AgentStatus.THINKING: 4, AgentStatus.COMPLETED: 5, AgentStatus.IDLE: 6, AgentStatus.OFFLINE: 7, AgentStatus.UNKNOWN: 8}


def aggregate_status(statuses: list[AgentStatus]) -> AgentStatus:
    return min(statuses, key=lambda status: STATUS_PRIORITY.get(status, 99)) if statuses else AgentStatus.OFFLINE


def aggregate_sessions(sessions: list[AgentSession]) -> AgentStatus:
    return aggregate_status([session.status for session in sessions])
