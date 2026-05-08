# `ws_recorder`

Reusable WebSocket metadata recorder for authorized capture workflows.

## When to Use

Use this module from optional skills that need a mitmproxy addon to record
WebSocket frame metadata. It is for triage only: by default it records host,
path, direction, text/binary flag, payload length, and first bytes as hex.

## Public API

- `build_ws_record(flow, message, dump_payload=False, max_payload=256, now=None)`
- `write_jsonl(record, out_path)`
- `WSRecorder`

`WSRecorder` is a mitmproxy addon class. `build_ws_record` and `write_jsonl`
are stdlib-only and are safe to unit test without mitmproxy installed.

## Security Posture

Safe defaults:

- Payload body is not dumped by default.
- Optional payload samples are base64 encoded and capped by `max_payload`.
- The caller must choose an output path; no env vars are read by this module.

Unsafe gate:

- `crowbar_dump_payload=true` includes a bounded payload sample. Use only for
  small redacted samples from authorized targets.
