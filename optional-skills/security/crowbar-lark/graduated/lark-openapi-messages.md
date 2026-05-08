# Lark OpenAPI Messages Extractor

Status: graduated for authorized message metadata extraction.

Use this path before HAR, mitmproxy, WebSocket, Protobuf, or Frida. It uses the official Lark/Feishu OpenAPI and writes normalized JSON.

## Authorization

Run only when the user confirms the Lark app/bot or token is authorized for the target chat. The credential principal must be able to read the requested conversation.

## Required Environment

Create a local `.env` from `optional-skills/security/crowbar-lark/.env.example` and fill authorized values:

```bash
LARK_BASE_URL=https://open.larksuite.com
LARK_APP_ID=cli_xxxxxxxxxxxxxxxxxxxx
LARK_APP_SECRET=replace-with-secret
LARK_CHAT_ID=oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Optional:

```bash
LARK_TENANT_ACCESS_TOKEN=t-xxxxxxxxxxxxxxxxxxxx
```

Prefer `LARK_APP_ID` and `LARK_APP_SECRET` for repeatable runs because the script fetches a fresh tenant token each time.

## Preflight

```bash
set -a; . ./.env; set +a
optional-skills/security/crowbar-lark/scripts/lark_preflight.py
```

Expected success shape:

```json
{
  "ok": true,
  "base_url": "https://open.larksuite.com",
  "list_chats": {
    "code": 0,
    "msg": "success"
  }
}
```

`accessible_chat_count` may be `0` even when direct target reads work, depending on app scopes and tenant policy. Treat direct extractor success or a specific API error as the authority.

## Run Command

Default safe metadata extraction:

```bash
RUN_DIR="crowbar-runs/lark-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN_DIR/artifacts"
set -a; . ./.env; set +a
optional-skills/security/crowbar-lark/scripts/lark_messages.py \
  --hours 24 \
  --limit 20 \
  --out "$RUN_DIR/artifacts/lark_messages.normalized.json"
```

The default output does not include message body content and redacts Lark IDs.

Use only when explicitly authorized:

```bash
--include-content
--include-raw-ids
```

## Expected Schema

Top level:

```json
{
  "source": "lark-openapi",
  "target": {},
  "captured_at": "ISO-8601",
  "window": {},
  "records": [],
  "redactions": [],
  "evidence": []
}
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

Empty windows are valid and should return `records: []`.

## Failure Modes

- `230002 Bot/User can NOT be out of the chat`: add the app/bot to the target chat, approve scopes, or switch to an authorized user-token flow.
- Token acquisition failure: verify `LARK_BASE_URL`, `LARK_APP_ID`, `LARK_APP_SECRET`, and tenant app status.
- Empty records: verify the time window first; do not treat it as failure unless the expected fixture says messages must exist.
- Expired pre-issued token: remove `LARK_TENANT_ACCESS_TOKEN` and use app id/secret so the script can fetch a fresh tenant token, or refresh the token externally.
- Permission or scope errors: record the Lark `code` and `msg` in `pitfalls/`, then fix app scopes or tenant approval before trying network capture.

## Validation

Focused tests:

```bash
scripts/run_tests.sh tests/skills/test_crowbar_lark.py
```

Skill hub regression:

```bash
scripts/run_tests.sh tests/tools/test_skills_hub.py
```

Manual stability check:

```bash
for i in 1 2 3; do
  optional-skills/security/crowbar-lark/scripts/lark_messages.py \
    --hours 24 \
    --limit 20 \
    --out "crowbar-runs/lark-stability/artifacts/lark_messages_run_${i}.json"
done
```

Graduation evidence from the first validated run:

```text
3 runs, each returned 12 metadata records.
Schemas matched.
No message content included.
IDs were redacted by default.
```
