# GitHub Official API First

Use official GitHub APIs before browser or capture workflows. This is more stable, auditable, and easier to graduate into reusable extractors.

## Credentials

Use environment variables only:

```bash
export GITHUB_TOKEN="github_pat_or_ghp_token"
export GITHUB_DEFAULT_OWNER="owner"
export GITHUB_DEFAULT_REPO="repo"
```

Never paste tokens into chat, commit them, or write them into fixtures.

## Issues PoC

Minimum target:

```text
Fetch recent issue metadata from one authorized repository and write normalized JSON.
```

Default behavior must be safe:

- No issue `body` unless `--include-content` is explicit.
- Author login is redacted unless `--include-raw-ids` is explicit.
- API errors must include GitHub status/code context without printing the token.

## If REST Fails

Record the precise failure before changing strategy:

- HTTP status
- GitHub `message`
- endpoint path
- token type and visible scope headers, redacted
- whether the repository is private or missing from the token scope

Then decide whether to adjust scopes, switch to GraphQL, or move to a UI-only path.
