---
name: github-export
description: Authenticated GitHub data export using the official REST and GraphQL APIs. Use when a user asks to export issues, pull requests, commits, or other repository metadata from a repository they own or are authorized to access; produce normalized JSON with safe defaults and graduate repeatable export scripts with tests.
---

# GitHub Export

## Why This Skill

Run authenticated GitHub data export against repositories the user owns or is authorized to access, with safe-by-default redaction and a documented run-evidence-test workflow. Produce normalized JSON output suitable for review, archival, and downstream tooling.

This skill is for authorized integrations only. It does not inspect, alter, or work around repository permissions; everything happens through GitHub's official OAuth-token API.

## When to Use

Use this skill when the user wants any of the following from a repository they own or are authorized to access:

- Recent issues metadata
- Pull request metadata
- Commit metadata
- Other REST or GraphQL endpoints with normalized JSON output
- A repeatable export script that can be re-run with stable schema

Start with the GitHub REST API. Use GraphQL only when REST cannot express the target efficiently.

## Authentication

Require a GitHub Personal Access Token (or App-installed token) with the minimum scopes required:

- For the default issues / PRs / commits export: a fine-grained PAT scoped to the target repository, read-only on **Metadata**, **Contents**, **Issues**, and **Pull requests**.
- For classic tokens on private repos, use the smallest read-equivalent `repo` scope your organization policy allows.

The token is read from environment variables only. It must never appear in chat, in commits, or in fixtures.

## Workflow

For each export target:

```text
target → authentication → script → run → tests → graduated
```

1. **target** — pick one specific endpoint family (e.g. issues for one repo).
2. **authentication** — confirm the user owns / can access the repo, and that the token's scopes are sufficient.
3. **script** — implement a small extractor under `scripts/` with safe defaults.
4. **run** — execute against the live target and write normalized JSON to a run directory under `runs/`.
5. **tests** — focused tests covering default redaction, explicit-content gates, error handling.
6. **graduated** — move a stable export under `graduated/` with required env, run command, expected schema, failure modes, and test command documented.

## Run Layout

Create a run directory for each export:

```bash
mkdir -p runs/github-$(date +%Y%m%d-%H%M%S)/{artifacts,extractors,tests,graduated}
```

Run output stays local; the `runs/` directory is git-ignored. Never commit tokens, raw private issue/PR body content, raw author logins (when redaction is appropriate), or any artifact that contains secrets.

Extractor output is normalized JSON with these top-level fields:

- `source` — endpoint family used (e.g. `github.rest.issues`)
- `target` — `{owner, repo}` (or other identifier shape)
- `captured_at` — ISO-8601 timestamp
- `records` — list of normalized records
- `redactions` — list of redactions applied
- `evidence` — references to corroborating run artifacts (see `references/github-openapi.md`)

## Default Safety

By default the extractor must:

- Omit issue / PR body content (only metadata fields go to `records`).
- Redact author logins to head + tail (`oct...cat`) unless the user explicitly opts in.
- Refuse to write any output that contains the token.
- Produce a clear error message on `401` (bad/expired token), `403` (forbidden / rate-limit), `404` (no access / wrong path), and `429` (rate-limit with `Retry-After` honored).

Explicit opt-in flags:

- `--include-content` — include the issue/PR body. Use only for repos you own.
- `--include-raw-ids` — include un-redacted author logins.

## References

- `references/github-openapi.md` — official API setup, scopes, normalized output shape.
- `graduated/github_issues.md` — created after the issues extractor graduates.

## Dependencies

No `_toolkit/` dependency yet. If a second integration skill repeats GitHub-API helpers (token redaction, rate-limit handling, normalized error reporting), extract those into `_toolkit/` per the conventions in `optional-skills/_toolkit/README.md` before duplicating.
