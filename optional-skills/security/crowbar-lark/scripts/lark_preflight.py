#!/usr/bin/env python3
"""Preflight Lark/Feishu OpenAPI credentials without printing secrets."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _json_request(method: str, url: str, headers: dict[str, str], body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    req_headers = dict(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json; charset=utf-8"
    req = Request(url, data=data, headers=req_headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"request failed: {exc}") from exc


def _token(base_url: str) -> str:
    existing = os.getenv("LARK_TENANT_ACCESS_TOKEN", "").strip()
    if existing:
        return existing
    app_id = os.getenv("LARK_APP_ID", "").strip() or os.getenv("FEISHU_APP_ID", "").strip()
    app_secret = os.getenv("LARK_APP_SECRET", "").strip() or os.getenv("FEISHU_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        raise RuntimeError("set LARK_TENANT_ACCESS_TOKEN or LARK_APP_ID/LARK_APP_SECRET")
    result = _json_request(
        "POST",
        f"{base_url}/open-apis/auth/v3/tenant_access_token/internal",
        {},
        {"app_id": app_id, "app_secret": app_secret},
    )
    if result.get("code") != 0:
        raise RuntimeError(f"token failed: code={result.get('code')} msg={result.get('msg')}")
    return result["tenant_access_token"]


def _redact(value: str) -> str:
    if len(value) <= 8:
        return "REDACTED"
    return f"{value[:4]}...{value[-4:]}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Lark/Feishu OpenAPI token and chat visibility.")
    parser.add_argument("--base-url", default=os.getenv("LARK_BASE_URL") or os.getenv("FEISHU_DOMAIN") or "https://open.larksuite.com")
    parser.add_argument("--chat-id", default=os.getenv("LARK_CHAT_ID", ""))
    parser.add_argument("--page-size", type=int, default=20)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    try:
        token = _token(base_url)
        headers = {"Authorization": f"Bearer {token}"}
        chats = _json_request(
            "GET",
            f"{base_url}/open-apis/im/v1/chats?{urlencode({'page_size': str(args.page_size)})}",
            headers,
        )
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    items = (chats.get("data") or {}).get("items") or []
    result: dict[str, Any] = {
        "ok": chats.get("code") == 0,
        "base_url": base_url,
        "list_chats": {
            "code": chats.get("code"),
            "msg": chats.get("msg"),
            "accessible_chat_count": len(items),
            "sample_chat_ids": [_redact(str(item.get("chat_id", ""))) for item in items[:5]],
        },
        "redactions": ["tenant_access_token", "app_secret", "chat_id"],
    }
    if args.chat_id:
        visible_ids = {str(item.get("chat_id", "")) for item in items}
        result["target_chat"] = {
            "chat_id": _redact(args.chat_id),
            "visible_in_list_chats_sample": args.chat_id in visible_ids,
        }

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
