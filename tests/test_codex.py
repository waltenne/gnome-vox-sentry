from pathlib import Path

from providers.codex.provider import CodexProvider
from vox_sentry.models import AgentStatus


def test_codex_provider_is_conservative_without_binary(monkeypatch, tmp_path):
    provider = CodexProvider(executable=None, codex_home=Path(tmp_path)); provider.executable = None
    monkeypatch.setattr(provider, "_processes", list)
    assert not provider.detect() and provider.get_sessions() == []


def test_codex_metadata_reader_only_reads_metadata_line(tmp_path):
    rollout = tmp_path / "sessions/2026/08/30"; rollout.mkdir(parents=True)
    (rollout / "rollout.jsonl").write_text('{"type":"session_meta","payload":{"session_id":"abc","cwd":"/tmp/project","model":"gpt-test","source":"cli"}}\n{"type":"response_item","payload":{"content":"secret"}}\n', encoding="utf-8")
    provider = CodexProvider(executable="/does/not/exist", codex_home=tmp_path)
    assert provider._recent_metadata("/tmp/project")["session_id"] == "abc"


def test_codex_detects_a_bundled_vscode_app_server_without_path_binary(monkeypatch, tmp_path):
    provider = CodexProvider(executable=None, codex_home=tmp_path)
    process = {"pid": 42, "argv": ["codex", "app-server"], "cwd": "/workspace", "app_server": True, "vscode": True, "originator": "codex_vscode"}
    monkeypatch.setattr(provider, "_processes", lambda: [process])
    monkeypatch.setattr(provider, "_active_rollout", lambda _pid: ({"session_id": "vscode-thread", "cwd": "/workspace", "source": "vscode"}, "task_started"))

    sessions = provider.get_sessions()

    assert provider.detect()
    assert len(sessions) == 1
    assert sessions[0].source.value == "vscode"
    assert sessions[0].status == AgentStatus.THINKING
    assert sessions[0].metadata["processKind"] == "vscode-app-server"


def test_codex_keeps_cli_and_vscode_sessions_separate(monkeypatch, tmp_path):
    provider = CodexProvider(executable="/usr/bin/codex", codex_home=tmp_path)
    processes = [
        {"pid": 10, "argv": ["codex"], "cwd": "/workspace/cli", "app_server": False, "vscode": False, "originator": None},
        {"pid": 20, "argv": ["codex", "app-server"], "cwd": "/home/user", "app_server": True, "vscode": True, "originator": "codex_vscode"},
    ]
    monkeypatch.setattr(provider, "_processes", lambda: processes)
    monkeypatch.setattr(provider, "_active_rollout", lambda pid: ({"session_id": f"thread-{pid}", "cwd": processes[pid == 20]["cwd"], "source": "vscode" if pid == 20 else "cli"}, "task_started" if pid == 20 else None))

    sessions = provider.get_sessions()

    assert {(session.pid, session.source.value) for session in sessions} == {(10, "cli"), (20, "vscode")}


def test_codex_app_server_reports_all_open_chats(monkeypatch, tmp_path):
    provider = CodexProvider(executable="/usr/bin/codex", codex_home=tmp_path)
    process = {"pid": 20, "argv": ["codex", "app-server"], "cwd": "/workspace", "app_server": True, "vscode": True, "originator": "codex_vscode"}
    monkeypatch.setattr(provider, "_processes", lambda: [process])
    monkeypatch.setattr(provider, "_active_rollouts", lambda _pid: [
        ({"session_id": "chat-idle", "cwd": "/workspace/idle", "source": "vscode"}, "task_complete"),
        ({"session_id": "chat-working", "cwd": "/workspace/working", "source": "vscode"}, "item_started"),
    ])
    monkeypatch.setattr(provider, "get_usage", lambda: None)

    sessions = provider.get_sessions()

    assert {session.id: session.status for session in sessions} == {
        "chat-idle": AgentStatus.IDLE,
        "chat-working": AgentStatus.WORKING,
    }
    assert provider.get_status(sessions) == AgentStatus.WORKING


def test_cli_status_follows_turn_events(monkeypatch, tmp_path):
    provider = CodexProvider(executable="/usr/bin/codex", codex_home=tmp_path)
    process = {"pid": 10, "argv": ["codex"], "cwd": "/workspace/cli", "app_server": False, "vscode": False, "originator": None}
    monkeypatch.setattr(provider, "_processes", lambda: [process])
    monkeypatch.setattr(provider, "_active_rollout", lambda _pid: ({"session_id": "cli-thread", "cwd": "/workspace/cli", "source": "cli"}, "task_started"))
    assert provider.get_sessions()[0].status == AgentStatus.THINKING

    monkeypatch.setattr(provider, "_active_rollout", lambda _pid: ({"session_id": "cli-thread", "cwd": "/workspace/cli", "source": "cli"}, "task_complete"))
    assert provider.get_sessions()[0].status == AgentStatus.IDLE


def test_rollout_lifecycle_does_not_treat_completed_items_as_idle_turn(tmp_path):
    rollout = tmp_path / "rollout.jsonl"
    rollout.write_text(
        '{"type":"event_msg","payload":{"type":"task_started"}}\n'
        '{"type":"response_item","payload":{"type":"reasoning","id":"r1"}}\n'
        '{"type":"event_msg","payload":{"type":"item_completed","item_id":"r1"}}\n'
        '{"type":"response_item","payload":{"type":"message","id":"m1"}}\n',
        encoding="utf-8",
    )
    provider = CodexProvider(executable="/usr/bin/codex", codex_home=tmp_path)

    assert provider._event_type_from_path(rollout) == "item_started"

    rollout.write_text(rollout.read_text(encoding="utf-8") + '{"type":"event_msg","payload":{"type":"task_complete"}}\n', encoding="utf-8")
    assert provider._event_type_from_path(rollout) == "task_complete"


def test_codex_usage_includes_windows_and_latest_daily_bucket(monkeypatch, tmp_path):
    provider = CodexProvider(executable="/usr/bin/codex", codex_home=tmp_path)
    monkeypatch.setattr("providers.codex.provider.time.strftime", lambda _format, _value: "2026-08-30")

    usage = provider._usage_from_account(
        {
            "rateLimits": {
                "planType": "plus",
                "primary": {"usedPercent": 79, "windowDurationMins": 300, "resetsAt": 100},
                "secondary": {"usedPercent": 13, "windowDurationMins": 10080, "resetsAt": 200},
            }
        },
        {
            "summary": {"lifetimeTokens": 9000000},
            "dailyUsageBuckets": [{"startDate": "2026-08-29", "tokens": 7000000}],
        },
    )

    assert usage is not None
    assert usage.session_percent == 79
    assert usage.limit_percent == 13
    assert usage.details["limitsAvailable"] is True
    assert usage.details["todayTokens"] is None
    assert usage.details["latestDailyTokens"] == 7000000
    assert usage.details["latestDailyDate"] == "2026-08-29"


def test_codex_usage_accepts_rate_limits_by_limit_id(tmp_path):
    provider = CodexProvider(executable="/usr/bin/codex", codex_home=tmp_path)
    usage = provider._usage_from_account(
        {"rateLimitsByLimitId": {"codex": {"primary": {"usedPercent": 10}}}},
        None,
    )

    assert usage is not None
    assert usage.session_percent == 10


def test_codex_status_becomes_rate_limited_when_a_window_is_exhausted(monkeypatch, tmp_path):
    provider = CodexProvider(executable="/usr/bin/codex", codex_home=tmp_path)
    process = {"pid": 10, "argv": ["codex"], "cwd": "/workspace", "app_server": False, "vscode": False, "originator": None}
    monkeypatch.setattr(provider, "_processes", lambda: [process])
    monkeypatch.setattr(provider, "_active_rollout", lambda _pid: ({"session_id": "thread", "cwd": "/workspace", "source": "cli"}, "task_started"))
    monkeypatch.setattr(provider, "get_usage", lambda: provider._usage_from_account(
        {"rateLimits": {"primary": {"usedPercent": 100}}}, None,
    ))

    assert provider.get_status() == AgentStatus.RATE_LIMITED
