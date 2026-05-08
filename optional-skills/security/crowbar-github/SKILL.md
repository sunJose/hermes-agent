---
name: crowbar-github
description: Evidence-first workflow for authorized GitHub repository data extraction. Use when a user asks to run a Crowbar-style PoC for GitHub, export issues, pull requests, or commits they are authorized to access, compare REST/GraphQL/API paths, or graduate a repeatable extractor with tests and pitfalls.
---

# Crowbar GitHub

## Why This Skill

Run authorized GitHub extraction work as a disciplined Crowbar pipeline: choose official APIs first, preserve evidence, build a minimal extractor, test repeatability, and only then graduate reusable assets.

Do not use this skill to bypass repository permissions, scrape private data without authorization, exfiltrate secrets, or evade organization policy. If authorization is unclear, stop and ask for the boundary before proceeding.

## When to Use

Use this skill for authorized GitHub targets such as:

- One repository's recent issues
- One repository's pull requests
- One repository's commits
- A REST or GraphQL response family that needs normalized extraction
- A second-target Crowbar validation after `crowbar-lark`

Start with official GitHub REST API. Use GraphQL only when REST cannot express the target efficiently. Do not move to browser/HAR capture unless official APIs cannot answer the authorized question.

## Authorization

Require one of:

- User owns the repository or organization.
- User administers the repository or organization.
- User has explicit permission to export the target data.
- User provides a GitHub token with read-only permissions for the requested repository data.

Use the least privileged token that works. For the default issues/PRs/commits PoC, prefer a fine-grained PAT scoped to the target repository with read-only Metadata, Contents, Issues, and Pull requests permissions.

## Pipeline

Use this order unless the user provides strong evidence that an earlier path cannot work:

```text
target -> authorization -> hypothesis -> evidence -> extractor -> test -> pitfalls -> graduated
```

For each hypothesis, state the expected evidence and the condition that disproves it. Prefer:

1. GitHub REST API
2. GitHub GraphQL API
3. GitHub CLI as a local wrapper
4. Browser/HAR capture only for authorized UI-only gaps

## Run Layout

Create a run directory for each PoC:

```bash
mkdir -p crowbar-runs/github-$(date +%Y%m%d-%H%M%S)/{artifacts,extractors,tests,pitfalls,graduated}
```

Store only redacted artifacts. Never commit tokens, raw private issue body content, raw author IDs if unsafe, cookies, or browser session material.

Extractor output must be normalized JSON with:

- `source`
- `target`
- `captured_at`
- `records`
- `redactions`
- `evidence`

## References

- `references/github-openapi.md` - official API-first setup and GitHub extractor notes.
- `graduated/github_issues.md` - created after the issues extractor graduates.

## Dependencies

No `_toolkit` dependency is required for the initial REST issues extractor. If a second Crowbar skill repeats GitHub's API safety helpers, extract them into `_toolkit/` under the P2 rules before duplicating further.
