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

## `evidence` Field Semantics

`evidence` is an array of evidence references attached to a normalized output.
It connects extractor output to the run notes that explain why the output is
trusted, how it was produced, and what was redacted.

Use `evidence: []` only when the output is an intermediate artifact that has
not been promoted, reviewed, or cited yet. A graduated output or report should
include at least one evidence reference.

Each evidence reference must use this shape:

```json
{
  "id": "EV-0001",
  "kind": "openapi-extractor-success",
  "artifact": "artifacts/evidence-openapi-success.json",
  "summary": "Official OpenAPI returned 12 metadata records with default redaction.",
  "supports": ["records", "redactions", "target"],
  "redactions": ["tenant_access_token", "container_id", "message_id"]
}
```

Fields:

- `id`: stable run-local evidence ID. Use `EV-0001`, `EV-0002`, etc.
- `kind`: evidence category, such as `openapi-preflight`,
  `openapi-extractor-success`, `permission-denied`, `schema-stability`,
  `websocket-metadata`, or `pitfall`.
- `artifact`: path relative to the run directory. Do not point at files outside
  the run directory unless the artifact is a committed reference document.
- `summary`: one sentence explaining what the evidence proves.
- `supports`: normalized output fields this evidence supports.
- `redactions`: redactions applied to the cited artifact.

When to fill `evidence`:

- Fill it for stability reports, graduated extractor outputs, and any artifact
  used as proof in `STATUS.md` or review notes.
- Fill it when a run fails in a useful way, for example a `230002` permission
  failure that becomes a pitfall.
- Leave it empty for one-off local probes that are not being cited.

Security rules:

- Evidence references must not contain raw tokens, cookies, secrets, raw chat
  IDs, raw message IDs, or message body content unless the run is explicitly
  authorized for content capture and the artifact remains local-only.
- If `--include-content` or `--include-raw-ids` was used, the evidence summary
  must say so explicitly and the artifact must not be committed.
