"""WebSocket metadata recorder with mitmproxy addon compatibility."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_ws_record(
    flow: Any,
    message: Any,
    *,
    dump_payload: bool = False,
    max_payload: int = 256,
    now: datetime | None = None,
) -> dict[str, Any]:
    payload = message.content or b""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    timestamp = now or datetime.now(timezone.utc)
    record: dict[str, Any] = {
        "captured_at": timestamp.isoformat(),
        "host": flow.request.pretty_host,
        "path": flow.request.path,
        "from_client": bool(message.from_client),
        "is_text": bool(message.is_text),
        "length": len(payload),
        "first16_hex": payload[:16].hex(),
    }
    if dump_payload:
        limit = max(0, int(max_payload))
        sample = payload[:limit]
        record["payload_sample_b64"] = base64.b64encode(sample).decode("ascii")
    return record


def write_jsonl(record: dict[str, Any], out_path: str | Path) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


class WSRecorder:
    """mitmproxy addon that records WebSocket metadata as JSONL."""

    def load(self, loader: Any) -> None:
        loader.add_option("crowbar_out", str, "artifacts/ws_frames.jsonl", "Output JSONL path for WebSocket metadata.")
        loader.add_option("crowbar_dump_payload", bool, False, "Include base64 payload samples. Keep false unless authorized.")
        loader.add_option("crowbar_max_payload", int, 256, "Maximum payload bytes to include when dumping is enabled.")

    def websocket_message(self, flow: Any) -> None:
        from mitmproxy import ctx

        message = flow.websocket.messages[-1]
        record = build_ws_record(
            flow,
            message,
            dump_payload=bool(ctx.options.crowbar_dump_payload),
            max_payload=int(ctx.options.crowbar_max_payload),
        )
        write_jsonl(record, ctx.options.crowbar_out)
