#!/usr/bin/env python3
"""Fetch recent Lark/Feishu messages through the official OpenAPI.

Credentials are read from environment variables:
  LARK_BASE_URL=https://open.larksuite.com or https://open.feishu.cn
  LARK_TENANT_ACCESS_TOKEN=...  # optional, preferred if already available
  LARK_APP_ID=...
  LARK_APP_SECRET=...

The script writes normalized JSON and avoids printing secrets.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _sensitive_values() -> list[str]:
    keys = [
        "LARK_APP_SECRET",
        "LARK_TENANT_ACCESS_TOKEN",
        "LARK_CHAT_ID",
        "FEISHU_APP_SECRET",
        "FEISHU_CHAT_ID",
    ]
    return [value for key in keys if (value := os.getenv(key, "").strip())]


def _sanitize_for_log(value: Any) -> str:
    text = str(value)
    for secret in _sensitive_values():
        if secret:
            text = text.replace(secret, "REDACTED")
    return text


def _json_request(method: str, url: str, headers: dict[str, str], body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    req_headers = dict(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json; charset=utf-8"
    req = Request(url, data=data, headers=req_headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8")
    except HTTPError as exc:
        detail = _sanitize_for_log(exc.read().decode("utf-8", errors="replace"))
        safe_url = _sanitize_for_log(url)
        raise RuntimeError(f"HTTP {exc.code} for {safe_url}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Request failed for {_sanitize_for_log(url)}: {_sanitize_for_log(exc)}") from exc
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response from {url}: {payload[:500]}") from exc


def _tenant_token(base_url: str) -> str:
    existing = os.getenv("LARK_TENANT_ACCESS_TOKEN", "").strip()
    if existing:
        return existing

    app_id = os.getenv("LARK_APP_ID", "").strip()
    app_secret = os.getenv("LARK_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        raise RuntimeError("Set LARK_TENANT_ACCESS_TOKEN or both LARK_APP_ID and LARK_APP_SECRET")

    url = f"{base_url}/open-apis/auth/v3/tenant_access_token/internal"
    body = {"app_id": app_id, "app_secret": app_secret}
    result = _json_request("POST", url, {}, body)
    if result.get("code") != 0:
        raise RuntimeError(
            f"Failed to get tenant token: code={result.get('code')} msg={_sanitize_for_log(result.get('msg'))}"
        )
    token = result.get("tenant_access_token")
    if not token:
        raise RuntimeError("Tenant token response did not include tenant_access_token")
    return token


def _redact_id(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "REDACTED"
    return f"{value[:4]}...{value[-4:]}"


def _normalize_message(item: dict[str, Any], include_content: bool, include_raw_ids: bool) -> dict[str, Any]:
    sender = item.get("sender", {}) if isinstance(item.get("sender"), dict) else {}
    def _id(value: Any) -> Any:
        if value is None or include_raw_ids:
            return value
        return _redact_id(str(value))

    record = {
        "message_id": _id(item.get("message_id")),
        "root_id": _id(item.get("root_id")),
        "parent_id": _id(item.get("parent_id")),
        "chat_id": _id(item.get("chat_id")),
        "msg_type": item.get("msg_type"),
        "create_time": item.get("create_time"),
        "update_time": item.get("update_time"),
        "sender_type": sender.get("sender_type"),
        "sender_id": _id(sender.get("id")),
    }
    if include_content:
        record["content"] = item.get("body", {}).get("content") if isinstance(item.get("body"), dict) else item.get("body")
    else:
        body = item.get("body", {})
        content = body.get("content") if isinstance(body, dict) else None
        record["content_present"] = bool(content)
        record["content_length"] = len(content) if isinstance(content, str) else None
    return record


def fetch_messages(args: argparse.Namespace) -> dict[str, Any]:
    base_url = args.base_url.rstrip("/")
    token = _tenant_token(base_url)
    end = int(time.time()) if args.end_time is None else args.end_time
    start = end - args.hours * 3600 if args.start_time is None else args.start_time

    records: list[dict[str, Any]] = []
    page_token = ""
    headers = {"Authorization": f"Bearer {token}"}

    while len(records) < args.limit:
        page_size = min(args.page_size, args.limit - len(records))
        query = {
            "container_id_type": args.container_id_type,
            "container_id": args.chat_id,
            "start_time": str(start),
            "end_time": str(end),
            "sort_type": args.sort_type,
            "page_size": str(page_size),
        }
        if page_token:
            query["page_token"] = page_token

        url = f"{base_url}/open-apis/im/v1/messages?{urlencode(query)}"
        result = _json_request("GET", url, headers)
        if result.get("code") != 0:
            raise RuntimeError(
                f"List messages failed: code={result.get('code')} msg={_sanitize_for_log(result.get('msg'))}"
            )

        data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
        items = data.get("items", []) if isinstance(data.get("items"), list) else []
        records.extend(_normalize_message(item, args.include_content, args.include_raw_ids) for item in items)

        if not data.get("has_more") or not data.get("page_token") or not items:
            break
        page_token = str(data["page_token"])

    return {
        "source": "lark-openapi",
        "target": {
            "base_url": base_url,
            "container_id_type": args.container_id_type,
            "container_id": _redact_id(args.chat_id),
        },
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "window": {"start_time": start, "end_time": end},
        "records": records[: args.limit],
        "redactions": ["Authorization", "tenant_access_token", "sender.id", "container_id", "message_id", "root_id", "parent_id", "chat_id"],
        "evidence": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch recent Lark/Feishu chat messages via official OpenAPI.")
    parser.add_argument("--base-url", default=os.getenv("LARK_BASE_URL", "https://open.larksuite.com"))
    parser.add_argument("--chat-id", default=os.getenv("LARK_CHAT_ID", ""), help="Authorized chat/container ID.")
    parser.add_argument("--container-id-type", default="chat")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--start-time", type=int)
    parser.add_argument("--end-time", type=int)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--sort-type", default="ByCreateTimeDesc")
    parser.add_argument("--include-content", action="store_true", help="Include message content in output. Defaults to metadata only.")
    parser.add_argument("--include-raw-ids", action="store_true", help="Write raw Lark IDs. Defaults to redacted IDs.")
    parser.add_argument("--out", required=True, help="Output JSON path.")
    args = parser.parse_args()

    if not args.chat_id:
        parser.error("--chat-id or LARK_CHAT_ID is required")
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.page_size < 1 or args.page_size > 50:
        parser.error("--page-size must be between 1 and 50")

    try:
        payload = fetch_messages(args)
    except RuntimeError as exc:
        print(f"error: {_sanitize_for_log(exc)}", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(payload['records'])} records to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
