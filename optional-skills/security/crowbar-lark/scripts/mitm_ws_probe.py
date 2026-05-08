"""mitmproxy addon for authorized Lark WebSocket triage.

Usage:
  mitmproxy -s SKILL_DIR/scripts/mitm_ws_probe.py \
    --set crowbar_out=artifacts/ws_frames.jsonl

Payload dumping is disabled by default. Enable only for small redacted samples:
  --set crowbar_dump_payload=true
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

from mitmproxy import ctx, websocket


class CrowbarWsProbe:
    def load(self, loader):
        loader.add_option("crowbar_out", str, "artifacts/ws_frames.jsonl", "Output JSONL path for WebSocket metadata.")
        loader.add_option("crowbar_dump_payload", bool, False, "Include base64 payload samples. Keep false unless authorized.")
        loader.add_option("crowbar_max_payload", int, 256, "Maximum payload bytes to include when dumping is enabled.")

    def websocket_message(self, flow):
        message: websocket.WebSocketMessage = flow.websocket.messages[-1]
        payload = message.content or b""
        record = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "host": flow.request.pretty_host,
            "path": flow.request.path,
            "from_client": message.from_client,
            "is_text": message.is_text,
            "length": len(payload),
            "first16_hex": payload[:16].hex(),
        }
        if ctx.options.crowbar_dump_payload:
            sample = payload[: max(0, ctx.options.crowbar_max_payload)]
            record["payload_sample_b64"] = base64.b64encode(sample).decode("ascii")

        out = Path(ctx.options.crowbar_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


addons = [CrowbarWsProbe()]
