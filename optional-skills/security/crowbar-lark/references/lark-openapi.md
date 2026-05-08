# Lark OpenAPI First

Use official APIs before client traffic analysis. This is more stable, auditable, and easier to graduate into reusable extractors.

## Platform Base

- Lark global: `https://open.larksuite.com`
- Feishu China: `https://open.feishu.cn`

Do not mix hosts. Ask the user which tenant they use if the URL or app console is unclear.

## Credentials

Use environment variables only:

```bash
export LARK_BASE_URL="https://open.larksuite.com"
export LARK_APP_ID="cli_..."
export LARK_APP_SECRET="..."
```

Alternatively, if the user already has a token:

```bash
export LARK_TENANT_ACCESS_TOKEN="t-..."
```

Never paste secrets into chat, commit them, or write them into fixtures.

## Message List PoC

Minimum target:

```text
Fetch recent N messages from one authorized chat and write normalized JSON.
```

Expected inputs:

- `chat_id` or another API-supported container ID
- time window or `--hours`
- page size and maximum records

Run preflight first:

```bash
python3 SKILL_DIR/scripts/lark_preflight.py --chat-id "$LARK_CHAT_ID"
```

If `accessible_chat_count` is `0`, add the app/bot to the target chat or switch to an authorized user-token flow before running the extractor.

Use `scripts/lark_messages.py`:

```bash
python3 SKILL_DIR/scripts/lark_messages.py \
  --chat-id "$LARK_CHAT_ID" \
  --hours 24 \
  --limit 50 \
  --out artifacts/lark_messages.normalized.json
```

## If OpenAPI Fails

Record the precise failure before changing strategy:

- HTTP status
- Lark error `code` and `msg`
- endpoint path
- scopes requested by the app
- whether tenant admin approval is required

Then decide whether to adjust scopes/app setup, use the official MCP, or move to Web/HAR capture.
