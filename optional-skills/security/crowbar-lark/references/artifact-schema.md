# Artifact Schema

Each run should have a directory:

```text
crowbar-runs/lark-YYYYMMDD-HHMMSS/
  artifacts/
  extractors/
  tests/
  pitfalls/
  graduated/
```

## Evidence Record

Use this shape for notes and JSON evidence:

```json
{
  "id": "EV-0001",
  "kind": "openapi-response",
  "source": "lark-openapi",
  "target": {
    "platform": "lark",
    "container_id_type": "chat",
    "container_id_redacted": "oc_...abcd"
  },
  "captured_at": "2026-05-07T00:00:00Z",
  "summary": "Fetched 20 recent messages with tenant token.",
  "artifact": "artifacts/lark_messages.normalized.json",
  "redactions": ["message.content", "sender.id", "tenant_access_token"]
}
```

## Normalized Extractor Output

```json
{
  "source": "lark-openapi",
  "target": {
    "container_id_type": "chat",
    "container_id": "REDACTED"
  },
  "captured_at": "2026-05-07T00:00:00Z",
  "records": [],
  "redactions": [],
  "evidence": []
}
```

Keep raw API responses separate from normalized output. Redact raw responses before sharing or committing.
