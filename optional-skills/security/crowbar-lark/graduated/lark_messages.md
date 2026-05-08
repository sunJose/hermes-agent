# Graduated Extractor: Lark Messages

Status: graduated for authorized metadata-only extraction through the official Lark OpenAPI.

This extractor is the default path for Lark message collection. Do not move to HAR, mitmproxy, WebSocket, Protobuf, or Frida unless this official API path cannot answer the authorized target question.

## Required Env

Use `optional-skills/security/crowbar-lark/.env.example` as the template:

```bash
LARK_BASE_URL=https://open.larksuite.com
LARK_APP_ID=replace-with-app-id
LARK_APP_SECRET=replace-with-app-secret
LARK_CHAT_ID=replace-with-chat-id
```

Constraints:

- Values must belong to an authorized Lark app and target chat.
- Do not commit `.env`, tenant tokens, raw chat IDs, or raw message IDs.
- Prefer app id/secret for repeatability; the extractor fetches a fresh tenant token per run.

## Run Cmd

Preflight:

```bash
set -a; . ./.env; set +a
optional-skills/security/crowbar-lark/scripts/lark_preflight.py
```

Metadata extraction:

```bash
RUN_DIR="crowbar-runs/lark-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN_DIR/artifacts"
set -a; . ./.env; set +a
optional-skills/security/crowbar-lark/scripts/lark_messages.py \
  --hours 24 \
  --limit 20 \
  --out "$RUN_DIR/artifacts/lark_messages.normalized.json"
```

Unsafe gates, only when explicitly authorized:

```bash
--include-content
--include-raw-ids
```

## Expected Schema

Top-level keys:

```text
captured_at
evidence
records
redactions
source
target
window
```

Default record keys:

```text
chat_id
content_length
content_present
create_time
message_id
msg_type
parent_id
root_id
sender_id
sender_type
update_time
```

Empty windows are valid and return:

```json
{
  "records": []
}
```

Real redacted expected JSON sample from the 2026-05-08 stability run:

```json
{
  "source": "lark-openapi",
  "target": {
    "base_url": "https://open.larksuite.com",
    "container_id_type": "chat",
    "container_id": "oc_0...ad83"
  },
  "window": {
    "start_time": 1778126645,
    "end_time": 1778213045
  },
  "records": [
    {
      "message_id": "om_x...c4fb",
      "root_id": null,
      "parent_id": null,
      "chat_id": "oc_0...ad83",
      "msg_type": "post",
      "create_time": "1778207223976",
      "update_time": "1778207223976",
      "sender_type": "app",
      "sender_id": "cli_...ded2",
      "content_present": true,
      "content_length": 4113
    }
  ],
  "redactions": [
    "Authorization",
    "tenant_access_token",
    "sender.id",
    "container_id",
    "message_id",
    "root_id",
    "parent_id",
    "chat_id"
  ],
  "evidence": []
}
```

## Failure Modes

- `230002 Bot/User can NOT be out of the chat`: the credential principal is not in the target chat, or the app lacks chat/message permissions.
- `HTTP 401` or `token expired`: remove stale `LARK_TENANT_ACCESS_TOKEN` if set, or refresh it externally; app id/secret mode fetches a fresh tenant token.
- Token acquisition failure: check `LARK_BASE_URL`, app id/secret, app enablement, and tenant admin approval.
- `records: []`: valid for an empty time window; verify the requested time range before treating it as a failure.
- Scope or tenant policy error: record the exact Lark `code` and `msg` in `pitfalls/` before trying lower-level capture.

## Test Cmd

Focused extractor tests:

```bash
scripts/run_tests.sh tests/optional_skills/test_lark_messages.py
```

Skill validation:

```bash
venv/bin/python /Users/macbook/.codex/skills/.system/skill-creator/scripts/quick_validate.py optional-skills/security/crowbar-lark
```

Manual stability check:

```bash
optional-skills/security/crowbar-lark/scripts/lark_messages.py --hours 24 --limit 20 --out "$RUN_DIR/artifacts/lark_messages_limit20_run1.json"
optional-skills/security/crowbar-lark/scripts/lark_messages.py --hours 24 --limit 20 --out "$RUN_DIR/artifacts/lark_messages_limit20_run2.json"
optional-skills/security/crowbar-lark/scripts/lark_messages.py --hours 24 --limit 50 --out "$RUN_DIR/artifacts/lark_messages_limit50_run3.json"
```

Latest validation summary:

```text
3 run artifacts generated locally under crowbar-runs/lark-stability-20260508-120404/
Record counts: 12, 12, 12
Schema matched across all runs.
No content field emitted.
IDs redacted by default.
```
