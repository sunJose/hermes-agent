# Lark Messages Stability Report - 2026-05-08

P1-5 validation for the official OpenAPI metadata extractor.

## Run Artifacts

The raw run artifacts are local-only under `crowbar-runs/` and are intentionally ignored by Git. They contain only redacted metadata in this run.

| Artifact | Records | Content Included | IDs Redacted | Target |
|---|---:|---|---|---|
| `crowbar-runs/lark-stability-20260508-120404/artifacts/lark_messages_limit20_run1.json` | 12 | False | True | `oc_0...ad83` |
| `crowbar-runs/lark-stability-20260508-120404/artifacts/lark_messages_limit20_run2.json` | 12 | False | True | `oc_0...ad83` |
| `crowbar-runs/lark-stability-20260508-120404/artifacts/lark_messages_limit50_run3.json` | 12 | False | True | `oc_0...ad83` |

## Schema Diff

- Schema matched across all 3 runs: `True`
- No `content` field was emitted in any run.
- Lark IDs were redacted by default in all records.

Record keys observed in all runs:

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

## Interpretation

- `limit 20` and `limit 50` both returned the same available 12-record window for this authorized chat.
- Empty pagination beyond 12 available records was handled by the extractor without schema drift.
- This validates the default safe path for metadata-only extraction; it does not validate `--include-content` for live data.
