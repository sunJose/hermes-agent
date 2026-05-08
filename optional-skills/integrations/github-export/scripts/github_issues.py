#!/usr/bin/env python3
"""Fetch GitHub issues through the official REST API.

Required env:
  GITHUB_TOKEN=github_pat_or_ghp_token
  GITHUB_DEFAULT_OWNER=owner
  GITHUB_DEFAULT_REPO=repo

Example:
  set -a; . ./.env; set +a
  RUN_DIR="runs/github-$(date +%Y%m%d-%H%M%S)"
  mkdir -p "$RUN_DIR/artifacts"
  optional-skills/integrations/github-export/scripts/github_issues.py \
    --limit 20 \
    --out "$RUN_DIR/artifacts/github_issues.normalized.json"

Defaults are safe: issue body and raw author logins are omitted unless
--include-content or --include-raw-ids are explicitly provided.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _sensitive_values() -> list[str]:
    keys = ["GITHUB_TOKEN"]
    return [value for key in keys if (value := os.getenv(key, "").strip())]


def _sanitize_for_log(value: Any) -> str:
    text = str(value)
    for secret in _sensitive_values():
        if secret:
            text = text.replace(secret, "REDACTED")
    return text


def _redact_id(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "REDACTED"
    keep = 3 if len(value) <= 10 else 4
    return f"{value[:keep]}...{value[-2:]}"


class GitHubAPIError(RuntimeError):
    def __init__(self, status: int, message: str, *, retry_after: str | None = None):
        self.status = status
        self.message = message
        self.retry_after = retry_after
        suffix = f" retry_after={retry_after}" if retry_after else ""
        super().__init__(f"GitHub API error: status={status} message={message}{suffix}")


def _json_request(url: str, token: str) -> tuple[dict[str, Any] | list[Any], dict[str, str]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "hermes-github-export",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8")
            response_headers = {k.lower(): v for k, v in resp.headers.items()}
    except HTTPError as exc:
        detail = _sanitize_for_log(exc.read().decode("utf-8", errors="replace"))
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        message = detail[:500]
        try:
            body = json.loads(detail)
            if isinstance(body, dict) and body.get("message"):
                message = str(body["message"])
        except json.JSONDecodeError:
            pass
        raise GitHubAPIError(exc.code, message, retry_after=retry_after) from exc
    except URLError as exc:
        raise RuntimeError(f"Request failed for {_sanitize_for_log(url)}: {_sanitize_for_log(exc)}") from exc

    try:
        return json.loads(payload), response_headers
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response from {_sanitize_for_log(url)}: {payload[:500]}") from exc


def _normalize_issue(item: dict[str, Any], *, include_content: bool, include_raw_ids: bool) -> dict[str, Any]:
    user = item.get("user") if isinstance(item.get("user"), dict) else {}
    login = str(user.get("login") or "")
    record = {
        "number": item.get("number"),
        "state": item.get("state"),
        "title": item.get("title"),
        "labels": [label.get("name") for label in item.get("labels", []) if isinstance(label, dict) and label.get("name")],
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "author": login if include_raw_ids else _redact_id(login),
        "is_pull_request": "pull_request" in item,
    }
    if include_content:
        record["body"] = item.get("body")
    else:
        body = item.get("body")
        record["body_present"] = bool(body)
        record["body_length"] = len(body) if isinstance(body, str) else None
    return record


def fetch_issues(args: argparse.Namespace) -> dict[str, Any]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Set GITHUB_TOKEN with read access to the target repository")

    owner = args.owner.strip()
    repo = args.repo.strip()
    if not owner or not repo:
        raise RuntimeError("Set --owner/--repo or GITHUB_DEFAULT_OWNER/GITHUB_DEFAULT_REPO")

    records: list[dict[str, Any]] = []
    page = 1
    headers_seen: dict[str, str] = {}
    per_page = min(args.per_page, args.limit)
    base = f"https://api.github.com/repos/{owner}/{repo}/issues"

    while len(records) < args.limit:
        query = {
            "state": args.state,
            "sort": args.sort,
            "direction": args.direction,
            "per_page": str(min(per_page, args.limit - len(records))),
            "page": str(page),
        }
        url = f"{base}?{urlencode(query)}"
        payload, response_headers = _json_request(url, token)
        headers_seen.update(response_headers)
        if not isinstance(payload, list):
            raise RuntimeError("GitHub issues response was not a JSON array")
        records.extend(
            _normalize_issue(item, include_content=args.include_content, include_raw_ids=args.include_raw_ids)
            for item in payload
            if isinstance(item, dict)
        )
        if len(payload) < int(query["per_page"]) or not payload:
            break
        page += 1

    return {
        "source": "github-rest",
        "target": {
            "owner": owner,
            "repo": repo,
            "resource": "issues",
        },
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "records": records[: args.limit],
        "redactions": ["Authorization", "GITHUB_TOKEN", "author.login", "issue.body"],
        "evidence": [],
        "rate_limit": {
            "limit": headers_seen.get("x-ratelimit-limit"),
            "remaining": headers_seen.get("x-ratelimit-remaining"),
            "reset": headers_seen.get("x-ratelimit-reset"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch authorized GitHub issue metadata via official REST API.")
    parser.add_argument("--owner", default=os.getenv("GITHUB_DEFAULT_OWNER", ""))
    parser.add_argument("--repo", default=os.getenv("GITHUB_DEFAULT_REPO", ""))
    parser.add_argument("--state", default="all", choices=["open", "closed", "all"])
    parser.add_argument("--sort", default="updated", choices=["created", "updated", "comments"])
    parser.add_argument("--direction", default="desc", choices=["asc", "desc"])
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--per-page", type=int, default=50)
    parser.add_argument("--include-content", action="store_true", help="Include issue body. Defaults to metadata only.")
    parser.add_argument("--include-raw-ids", action="store_true", help="Write raw author logins. Defaults to redacted logins.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.per_page < 1 or args.per_page > 100:
        parser.error("--per-page must be between 1 and 100")

    try:
        payload = fetch_issues(args)
    except (RuntimeError, GitHubAPIError) as exc:
        print(f"error: {_sanitize_for_log(exc)}", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(payload['records'])} records to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
