---
name: crowbar-lark
description: Evidence-first workflow for authorized Lark data extraction and protocol triage. Use when a user asks to run a Crowbar-style PoC for Lark/Feishu, export messages or collaboration data they are authorized to access, compare OpenAPI versus Web/HAR/mitmproxy capture paths, analyze WebSocket or Protobuf artifacts, or graduate a repeatable extractor with tests and pitfalls.
---

# Crowbar Lark

## Overview

Run authorized Lark extraction work as a disciplined Crowbar pipeline: choose the least invasive path first, preserve evidence, build a minimal extractor, test repeatability, and only then graduate reusable assets.

Do not use this skill to bypass authorization, defeat platform protections, extract other users' data, or evade tenant policy. If authorization is unclear, stop and ask for the boundary before proceeding.

## Workflow

Use this order unless the user provides strong evidence that an earlier path cannot work:

```text
target -> authorization -> hypothesis -> evidence -> extractor -> test -> pitfalls -> graduated
```

### 1. Target

Narrow the PoC to one concrete object:

- One chat's recent N messages
- One document's exported content or comments
- One WebSocket stream sample
- One suspected Protobuf frame family

Record the platform base: Lark global (`open.larksuite.com`) or Feishu China (`open.feishu.cn`). Do not assume they are interchangeable.

### 2. Authorization

Require one of:

- User owns the account and target data.
- User administers the tenant or app.
- User has explicit written permission for the target.
- User provides an official app token with scopes for the requested data.

Prefer official OpenAPI/MCP. Use Web/HAR/mitmproxy only when official APIs do not cover the target or when the task is explicitly client-path triage. Use Frida only after capture/static evidence shows the needed plaintext is available only at runtime.

### 3. Hypothesis

List possible paths and rank them:

1. Official Lark OpenAPI or official Lark OpenAPI MCP
2. Lark Web plus DevTools HAR/exported responses
3. mitmproxy regular or local capture for HTTP/WebSocket metadata
4. Static analysis of client resources for schemas, routes, or descriptors
5. Runtime instrumentation for authorized debugging

For each hypothesis, state the expected evidence and the condition that disproves it.

### 4. Evidence

Create an evidence directory for each run:

```bash
mkdir -p crowbar-runs/lark-$(date +%Y%m%d-%H%M%S)/{artifacts,extractors,tests,pitfalls,graduated}
```

Store only redacted artifacts. Never commit tokens, cookies, session IDs, private message content, or certificate material.

### 5. Extractor

Start with `scripts/lark_preflight.py` to verify token validity and chat visibility without printing secrets. Then use `scripts/lark_messages.py` for official message-list extraction. Use `scripts/mitm_ws_probe.py` only for authorized WebSocket capture triage and keep payload dumping disabled unless the user explicitly needs a small redacted sample.

Extractor output must be normalized JSON with:

- `source`
- `target`
- `captured_at`
- `records`
- `redactions`
- `evidence`

### 6. Test

Before promoting an extractor, verify:

- It can run twice with the same target and produce the same schema.
- It handles empty result sets.
- It does not print secrets.
- It writes raw artifacts only when explicitly requested.
- A redacted fixture can be used without network access.

### 7. Pitfalls

Append every blocker to `pitfalls/` with:

```text
symptom:
evidence:
root_cause:
fix_or_next_probe:
reusable_rule:
```

Common pitfalls: wrong Lark/Feishu base URL, missing app scopes, tenant admin approval missing, desktop client not using system proxy, TLS pinning, binary WebSocket frames compressed before Protobuf, Protobuf schema unavailable, and confusing `ssl_insecure` with client CA trust.

### 8. Graduated

Move an extractor to `graduated/` only when it has:

- Clear authorization assumptions
- Reproduction steps
- Required environment variables
- Redacted input fixture
- Expected output sample
- Minimal test command

## References

- `references/lark-openapi.md` - official API-first setup and message extraction notes.
- `references/capture-paths.md` - Web, HAR, mitmproxy, WebSocket, Protobuf, and runtime triage order.
- `references/artifact-schema.md` - run directory and JSON evidence conventions.
- `graduated/lark-openapi-messages.md` - validated official OpenAPI message metadata extractor path.

## Dependencies

- `_toolkit/ws_recorder` (>=0.1) - authorized WebSocket metadata recording; used by `scripts/mitm_ws_probe.py`.

## Scripts

- `scripts/lark_messages.py` - fetch recent messages from the official Lark/Feishu OpenAPI using environment variables.
- `scripts/lark_preflight.py` - verify official OpenAPI credentials and chat visibility without exposing secrets.
- `scripts/mitm_ws_probe.py` - mitmproxy addon for recording authorized WebSocket metadata and optional redacted payload samples.
