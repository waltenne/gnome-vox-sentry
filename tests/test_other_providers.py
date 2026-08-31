import json
import sqlite3

from providers.claude import ClaudeProvider
from providers.copilot import CopilotProvider
from providers.opencode import OpenCodeProvider
from vox_sentry.models import AgentStatus


def _process(pid, argv, cwd="/workspace/project", **extra):
    return {
        "pid": pid,
        "ppid": 1,
        "argv": argv,
        "command": " ".join(argv).lower(),
        "executable": argv[0],
        "cwd": cwd,
        "environment_keys": set(),
        "vscode": False,
        **extra,
    }


def test_claude_cli_uses_recent_session_file(monkeypatch, tmp_path):
    sessions = tmp_path / "projects/project"
    sessions.mkdir(parents=True)
    (sessions / "session-id.jsonl").write_text('{"type":"user","message":"private"}\n', encoding="utf-8")
    provider = ClaudeProvider(executable="/does/not/exist", claude_home=tmp_path)
    monkeypatch.setattr(provider, "_processes", lambda: [_process(41, ["claude"])])
    monkeypatch.setattr("providers.claude.provider.is_recent", lambda _path, _seconds: True)

    session = provider.get_sessions()[0]

    assert session.id == "session-id"
    assert session.status == AgentStatus.WORKING
    assert session.source.value == "cli"
    assert "private" not in str(session.metadata)


def test_claude_last_prompt_marker_after_completed_turn_is_idle(monkeypatch, tmp_path):
    sessions = tmp_path / "projects/project"
    sessions.mkdir(parents=True)
    path = sessions / "session-id.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({
                    "type": "assistant",
                    "message": {"stop_reason": "end_turn", "content": [{"type": "text", "text": "done"}]},
                }),
                json.dumps({"type": "last-prompt", "lastPrompt": 'text containing "type":"user"'}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    provider = ClaudeProvider(executable="/does/not/exist", claude_home=tmp_path)
    monkeypatch.setattr(provider, "_processes", lambda: [_process(42, ["claude"])])
    monkeypatch.setattr("providers.claude.provider.is_recent", lambda _path, _seconds: False)

    session = provider.get_sessions()[0]

    assert session.status == AgentStatus.IDLE


def test_copilot_cli_and_vscode_are_separate(monkeypatch, tmp_path):
    provider = CopilotProvider(executable="/does/not/exist", copilot_home=tmp_path)
    processes = [
        _process(51, ["copilot"]),
        _process(52, ["copilot"], vscode=True),
    ]
    monkeypatch.setattr(provider, "_processes", lambda: processes)

    sessions = provider.get_sessions()

    assert {(item.pid, item.source.value) for item in sessions} == {(51, "cli"), (52, "vscode")}


def test_opencode_reads_session_metadata_without_message_rows(monkeypatch, tmp_path):
    database = tmp_path / "opencode.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE session (id text, directory text, time_created integer, "
            "time_updated integer, model text)"
        )
        connection.execute(
            "INSERT INTO session VALUES (?, ?, ?, ?, ?)",
            ("ses-test", "/workspace/project", 1000, 2000, "anthropic/claude-sonnet"),
        )
    provider = OpenCodeProvider(executable="/does/not/exist", data_dir=tmp_path)
    process = _process(61, ["opencode"], model=None)
    monkeypatch.setattr(provider, "_processes", lambda: [process])
    monkeypatch.setattr("providers.opencode.provider.datetime", __import__("datetime").datetime)

    session = provider.get_sessions()[0]

    assert session.id == "ses-test"
    assert session.model == "anthropic/claude-sonnet"
    assert session.status == AgentStatus.IDLE
