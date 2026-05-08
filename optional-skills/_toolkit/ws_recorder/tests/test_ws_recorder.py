from datetime import datetime, timezone
from pathlib import Path
import sys
from types import SimpleNamespace

# tests -> ws_recorder -> _toolkit
_TOOLKIT = Path(__file__).resolve().parents[2]
if str(_TOOLKIT) not in sys.path:
    sys.path.insert(0, str(_TOOLKIT))

from ws_recorder import build_ws_record, write_jsonl


def _flow():
    return SimpleNamespace(request=SimpleNamespace(pretty_host="example.test", path="/ws"))


def _message(content=b"\x08\x96\x01hello", from_client=True, is_text=False):
    return SimpleNamespace(content=content, from_client=from_client, is_text=is_text)


def test_build_ws_record_defaults_to_metadata_only():
    record = build_ws_record(
        _flow(),
        _message(),
        now=datetime(2026, 5, 8, tzinfo=timezone.utc),
    )

    assert record == {
        "captured_at": "2026-05-08T00:00:00+00:00",
        "host": "example.test",
        "path": "/ws",
        "from_client": True,
        "is_text": False,
        "length": 8,
        "first16_hex": "08960168656c6c6f",
    }


def test_build_ws_record_payload_dump_is_explicit_and_capped():
    record = build_ws_record(
        _flow(),
        _message(content=b"secret-payload"),
        dump_payload=True,
        max_payload=6,
        now=datetime(2026, 5, 8, tzinfo=timezone.utc),
    )

    assert record["payload_sample_b64"] == "c2VjcmV0"
    assert record["length"] == len(b"secret-payload")


def test_write_jsonl_appends(tmp_path):
    out = tmp_path / "frames.jsonl"
    write_jsonl({"a": 1}, out)
    write_jsonl({"b": 2}, out)

    assert out.read_text(encoding="utf-8").splitlines() == ['{"a": 1}', '{"b": 2}']
