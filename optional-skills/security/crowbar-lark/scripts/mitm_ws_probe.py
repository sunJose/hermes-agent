"""mitmproxy addon for authorized Lark WebSocket triage.

Usage:
  mitmproxy -s SKILL_DIR/scripts/mitm_ws_probe.py \
    --set crowbar_out=artifacts/ws_frames.jsonl

Payload dumping is disabled by default. Enable only for small redacted samples:
  --set crowbar_dump_payload=true
"""

from __future__ import annotations

from pathlib import Path
import sys

# scripts -> crowbar-lark -> security -> optional-skills
_TOOLKIT = Path(__file__).resolve().parents[3] / "_toolkit"
if str(_TOOLKIT) not in sys.path:
    sys.path.insert(0, str(_TOOLKIT))

from ws_recorder import WSRecorder


addons = [WSRecorder()]
