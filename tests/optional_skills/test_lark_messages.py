import importlib.util
import sys
from argparse import Namespace
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "optional-skills"
    / "security"
    / "crowbar-lark"
    / "scripts"
    / "lark_messages.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("crowbar_lark_messages", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _args(**overrides):
    values = {
        "base_url": "https://open.larksuite.com",
        "chat_id": "oc_targetchatsecret1234567890",
        "container_id_type": "chat",
        "hours": 24,
        "start_time": 100,
        "end_time": 200,
        "limit": 10,
        "page_size": 10,
        "sort_type": "ByCreateTimeDesc",
        "include_content": False,
        "include_raw_ids": False,
    }
    values.update(overrides)
    return Namespace(**values)


def _message():
    return {
        "message_id": "om_messageidsecret1234567890",
        "root_id": "om_rootidsecret1234567890",
        "parent_id": "om_parentidsecret1234567890",
        "chat_id": "oc_targetchatsecret1234567890",
        "msg_type": "post",
        "create_time": "1778205339778",
        "update_time": "1778205339778",
        "sender": {"sender_type": "app", "id": "cli_sendersecret1234567890"},
        "body": {"content": '{"title":"private","content":[[{"tag":"text","text":"secret body"}]]}'},
    }


def _fake_success_response(message=None):
    return {
        "code": 0,
        "data": {
            "items": [_message() if message is None else message],
            "has_more": False,
        },
    }


def test_default_output_omits_content(monkeypatch):
    module = _load_module()
    monkeypatch.setenv("LARK_TENANT_ACCESS_TOKEN", "tenant-token-secret")
    monkeypatch.setattr(module, "_json_request", lambda *args, **kwargs: _fake_success_response())

    payload = module.fetch_messages(_args())
    record = payload["records"][0]

    assert "content" not in record
    assert record["content_present"] is True
    assert record["content_length"] > 0


def test_default_output_redacts_ids(monkeypatch):
    module = _load_module()
    monkeypatch.setenv("LARK_TENANT_ACCESS_TOKEN", "tenant-token-secret")
    monkeypatch.setattr(module, "_json_request", lambda *args, **kwargs: _fake_success_response())

    payload = module.fetch_messages(_args())
    record = payload["records"][0]

    assert record["message_id"] == "om_m...7890"
    assert record["root_id"] == "om_r...7890"
    assert record["parent_id"] == "om_p...7890"
    assert record["chat_id"] == "oc_t...7890"
    assert record["sender_id"] == "cli_...7890"
    assert payload["target"]["container_id"] == "oc_t...7890"


def test_include_content_gate(monkeypatch):
    module = _load_module()
    monkeypatch.setenv("LARK_TENANT_ACCESS_TOKEN", "tenant-token-secret")
    monkeypatch.setattr(module, "_json_request", lambda *args, **kwargs: _fake_success_response())

    payload = module.fetch_messages(_args(include_content=True))
    record = payload["records"][0]

    assert "content" in record
    assert "secret body" in record["content"]
    assert "content_present" not in record


def test_api_error_message_is_clear(monkeypatch, tmp_path, capsys):
    module = _load_module()
    monkeypatch.setenv("LARK_APP_ID", "cli_test")
    monkeypatch.setenv("LARK_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("LARK_CHAT_ID", "oc_targetchatsecret1234567890")

    def fake_request(method, url, headers, body=None):
        if "tenant_access_token" in url:
            return {"code": 0, "tenant_access_token": "tenant-token-secret"}
        return {"code": 230002, "msg": "Bot/User can NOT be out of the chat"}

    monkeypatch.setattr(module, "_json_request", fake_request)
    out = tmp_path / "messages.json"
    monkeypatch.setattr(sys, "argv", ["lark_messages.py", "--out", str(out)])

    assert module.main() == 1
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "230002" in combined
    assert "Bot/User can NOT be out of the chat" in combined
    assert not out.exists()


def test_stdout_stderr_do_not_leak_lark_app_secret(monkeypatch, tmp_path, capsys):
    module = _load_module()
    secret = "literal-lark-app-secret-value"
    monkeypatch.setenv("LARK_APP_ID", "cli_test")
    monkeypatch.setenv("LARK_APP_SECRET", secret)
    monkeypatch.setenv("LARK_CHAT_ID", "oc_targetchatsecret1234567890")

    def fake_request(method, url, headers, body=None):
        if "tenant_access_token" in url:
            return {"code": 0, "tenant_access_token": "tenant-token-secret"}
        return _fake_success_response()

    monkeypatch.setattr(module, "_json_request", fake_request)
    out = tmp_path / "messages.json"
    monkeypatch.setattr(sys, "argv", ["lark_messages.py", "--out", str(out)])

    assert module.main() == 0
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert secret not in combined
    assert out.exists()


def test_empty_window_returns_empty_records(monkeypatch):
    module = _load_module()
    monkeypatch.setenv("LARK_TENANT_ACCESS_TOKEN", "tenant-token-secret")

    def fake_request(method, url, headers, body=None):
        assert "start_time=100" in url
        assert "end_time=100" in url
        return {"code": 0, "data": {"items": [], "has_more": False}}

    monkeypatch.setattr(module, "_json_request", fake_request)

    payload = module.fetch_messages(_args(start_time=100, end_time=100))

    assert payload["records"] == []
    assert payload["window"] == {"start_time": 100, "end_time": 100}


def test_expired_token_401_is_reported_clearly(monkeypatch, tmp_path, capsys):
    module = _load_module()
    monkeypatch.setenv("LARK_TENANT_ACCESS_TOKEN", "expired-token-secret")
    monkeypatch.setenv("LARK_CHAT_ID", "oc_targetchatsecret1234567890")

    def fake_request(method, url, headers, body=None):
        raise RuntimeError('HTTP 401 for https://open.larksuite.com/open-apis/im/v1/messages: {"msg":"token expired"}')

    monkeypatch.setattr(module, "_json_request", fake_request)
    out = tmp_path / "messages.json"
    monkeypatch.setattr(sys, "argv", ["lark_messages.py", "--out", str(out)])

    assert module.main() == 1
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "HTTP 401" in combined
    assert "token expired" in combined
    assert "expired-token-secret" not in combined
    assert not out.exists()
