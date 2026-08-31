import json

from providers.antigravity.provider import AntigravityProvider
from providers.gemini.provider import GeminiProvider
from vox_sentry.models import AgentStatus


def test_gemini_cli_reads_header_without_message_content(monkeypatch, tmp_path):
    chats = tmp_path / "tmp/project/chats"
    chats.mkdir(parents=True)
    session = chats / "session.jsonl"
    session.write_text(
        '{"kind":"main","sessionId":"gemini-session","projectHash":"hash",'
        '"startTime":"2026-08-30T12:00:00Z","lastUpdated":"2026-08-30T12:00:00Z"}\n'
        '{"$set":{"messages":[{"role":"user","content":"private prompt"}]}}\n',
        encoding="utf-8",
    )
    provider = GeminiProvider(executable="/does/not/exist", gemini_home=tmp_path)
    monkeypatch.setattr(
        provider,
        "_processes",
        lambda: [
            {
                "pid": 11,
                "argv": ["gemini"],
                "cwd": "/workspace/project",
                "vscode": False,
            }
        ],
    )
    monkeypatch.setattr(provider, "_is_recent", lambda _path: False)

    sessions = provider.get_sessions()

    assert sessions[0].id == "gemini-session"
    assert sessions[0].source.value == "cli"
    assert sessions[0].status == AgentStatus.IDLE
    assert "private prompt" not in str(sessions[0].metadata)


def test_gemini_finds_nvm_install_when_service_path_is_minimal(monkeypatch, tmp_path):
    provider = GeminiProvider(executable="/does/not/exist", gemini_home=tmp_path)
    monkeypatch.setattr("providers.gemini.provider.shutil.which", lambda _name: None)
    monkeypatch.setattr("providers.gemini.provider.Path.home", lambda: tmp_path)
    executable = tmp_path / ".nvm/versions/node/v24.0.0/bin/gemini"
    executable.parent.mkdir(parents=True)
    executable.touch()

    assert provider._find_executable() == str(executable)


def test_gemini_a2a_process_is_vscode(monkeypatch, tmp_path):
    provider = GeminiProvider(executable="/does/not/exist", gemini_home=tmp_path)
    monkeypatch.setattr(
        provider,
        "_processes",
        lambda: [
            {
                "pid": 12,
                "argv": ["node", "gemini", "a2a-server"],
                "cwd": "/workspace/project",
                "vscode": True,
            }
        ],
    )
    sessions = provider.get_sessions()
    assert sessions[0].source.value == "vscode"
    assert sessions[0].metadata["processKind"] == "vscode-a2a"


def test_gemini_does_not_match_a_shell_containing_the_package_name(monkeypatch):
    provider = GeminiProvider(executable="/does/not/exist")
    monkeypatch.setattr(
        "providers.gemini.provider.process_snapshot",
        lambda: [
            {
                "pid": 13,
                "ppid": 1,
                "argv": ["zsh", "-lc", "echo @google/gemini-cli"],
                "command": "zsh -lc echo @google/gemini-cli",
                "executable": "zsh",
                "cwd": "/workspace",
                "environment_keys": set(),
            }
        ],
    )
    assert provider._processes() == []


def test_antigravity_hub_is_idle_and_worker_is_working(monkeypatch):
    provider = AntigravityProvider(executable="/does/not/exist")
    processes = [
        {"pid": 20, "ppid": 1, "argv": ["agy", "--hub"], "command": "agy --hub", "vscode": True, "cwd": "/workspace"},
        {"pid": 21, "ppid": 20, "argv": ["agy", "--agent"], "command": "agy --agent", "vscode": True, "cwd": "/workspace"},
    ]
    monkeypatch.setattr(provider, "_processes", lambda _processes=None: processes)
    monkeypatch.setattr("providers.antigravity.provider.process_snapshot", lambda: processes)
    monkeypatch.setattr(provider, "_log_state", lambda _pid: None)
    monkeypatch.setattr(provider, "_conversation_state", lambda _process: None)

    sessions = provider.get_sessions()

    assert len(sessions) == 1
    assert sessions[0].status == AgentStatus.WORKING
    assert sessions[0].source.value == "vscode"


def test_antigravity_background_hub_is_not_a_session(monkeypatch):
    provider = AntigravityProvider(executable="/does/not/exist")
    processes = [
        {
            "pid": 22,
            "ppid": 1,
            "argv": ["agy", "--hub"],
            "command": "agy --hub",
            "vscode": True,
            "cwd": "/workspace",
        }
    ]
    monkeypatch.setattr(provider, "_processes", lambda _processes=None: processes)
    monkeypatch.setattr("providers.antigravity.provider.process_snapshot", lambda: processes)
    monkeypatch.setattr(provider, "_recent_log_state", lambda _pid: None)

    assert provider.get_sessions() == []
    assert provider.get_status() == AgentStatus.OFFLINE


def test_antigravity_does_not_match_a_shell_containing_the_word(monkeypatch):
    provider = AntigravityProvider(executable="/does/not/exist")
    monkeypatch.setattr(
        "providers.antigravity.provider.process_snapshot",
        lambda: [
            {
                "pid": 30,
                "ppid": 1,
                "argv": ["zsh", "-lc", "echo antigravity"],
                "command": "zsh -lc echo antigravity",
                "executable": "zsh",
                "cwd": "/workspace",
                "environment_keys": set(),
            }
        ],
    )
    assert provider._processes() == []


def test_antigravity_log_state_changes_from_working_to_idle(monkeypatch, tmp_path):
    provider = AntigravityProvider(executable="/does/not/exist")
    log = tmp_path / "cli.log"
    log.write_text("I0830 15:00:00.000 server.go: Sending user message\n", encoding="utf-8")
    monkeypatch.setattr(provider, "_log_path", lambda _pid: log)
    assert provider._log_state(99) == "working"

    log.write_text(
        "I0830 15:00:00.000 server.go: Sending user message\n"
        "I0830 15:00:01.000 manager.go: Full redraw completed\n",
        encoding="utf-8",
    )
    assert provider._log_state(99) == "idle"


def test_antigravity_reads_shared_quota_summary(monkeypatch, tmp_path):
    provider = AntigravityProvider(executable="/does/not/exist", gemini_home=tmp_path)
    provider._credentials = lambda: {"access_token": "test-token", "expiry_date": 4_000_000_000_000}
    responses = {
        "loadCodeAssist": {"cloudaicompanionProject": "aicode-consumers"},
        "retrieveUserQuotaSummary": {
            "groups": [
                {
                    "displayName": "Gemini Models",
                    "buckets": [
                        {"bucketId": "gemini-5h", "remainingFraction": 0.81, "resetTime": "2026-08-31T15:00:00Z"},
                        {"bucketId": "gemini-weekly", "remainingFraction": 0.64, "resetTime": "2026-09-05T15:00:00Z"},
                    ],
                },
                {
                    "displayName": "Claude and GPT models",
                    "buckets": [
                        {"bucketId": "3p-5h", "remainingFraction": 0.92, "resetTime": "2026-08-31T15:00:00Z"},
                        {"bucketId": "3p-weekly", "remainingFraction": 0.77, "resetTime": "2026-09-05T15:00:00Z"},
                    ],
                },
            ]
        },
    }
    monkeypatch.setattr(
        provider,
        "_post_json",
        lambda endpoint, token, payload: next(
            (value for key, value in responses.items() if endpoint.endswith(key)), None
        ),
    )

    usage = provider.get_usage()

    assert provider.get_capabilities().to_dict()["usage"] is True
    assert usage is not None
    assert usage.session_percent == 19.0
    assert usage.limit_percent == 36.0
    assert usage.details["primary"]["resetTime"] == "2026-08-31T15:00:00Z"
    assert usage.details["secondary"]["resetTime"] == "2026-09-05T15:00:00Z"


def test_antigravity_prefers_official_cli_usage_output(monkeypatch, tmp_path):
    provider = AntigravityProvider(executable="/usr/bin/agy", gemini_home=tmp_path)
    output = {
        "command": {
            "name": "usage",
            "data": {
                "groups": [
                    {
                        "name": "Gemini Models",
                        "buckets": [
                            {"id": "gemini-weekly", "window": "weekly", "remaining_fraction": 0.90, "reset_time": "2026-09-06T00:00:00Z"},
                            {"id": "gemini-5h", "window": "5h", "remaining_fraction": 0.75, "reset_time": "2026-08-31T15:00:00Z"},
                        ],
                    }
                ]
            },
        }
    }

    class Result:
        returncode = 0
        stdout = json.dumps(output) + "\n"

    monkeypatch.setattr("providers.antigravity.provider.subprocess.run", lambda *args, **kwargs: Result())
    usage = provider.get_usage()

    assert usage is not None
    assert usage.details["source"] == "antigravity_cli_usage"
    assert usage.session_percent == 25.0
    assert usage.limit_percent == 10.0


def test_antigravity_falls_back_to_model_quota(monkeypatch, tmp_path):
    provider = AntigravityProvider(executable="/does/not/exist", gemini_home=tmp_path)
    provider._credentials = lambda: {"access_token": "test-token"}

    def post(endpoint, _token, _payload):
        if endpoint.endswith("loadCodeAssist"):
            return {"cloudaicompanionProject": "aicode-consumers"}
        if endpoint.endswith("fetchAvailableModels"):
            return {
                "models": {
                    "gemini-3-flash": {
                        "displayName": "Gemini Flash",
                        "quotaInfo": {"remainingFraction": 0.73, "resetTime": "2026-09-01T00:00:00Z"},
                    }
                }
            }
        return None

    monkeypatch.setattr(provider, "_post_json", post)
    usage = provider.get_usage()

    assert usage is not None
    assert usage.session_percent == 27.0
    assert usage.details["source"] == "antigravity_cloud_code_models"


def test_antigravity_rejects_expired_usage_token(monkeypatch, tmp_path):
    provider = AntigravityProvider(executable="/does/not/exist", gemini_home=tmp_path)
    provider._credentials = lambda: {"access_token": "expired", "expiry_date": 1}
    called = False

    def post(*_args):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(provider, "_post_json", post)

    assert provider.get_usage() is None
    assert called is False
