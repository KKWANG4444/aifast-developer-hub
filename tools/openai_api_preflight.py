#!/usr/bin/env python3
"""Offline OpenAI-compatible endpoint preflight checker.

Validates URL construction and optionally performs safe network checks. API keys are
read from the environment and never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass
class CheckResult:
    name: str
    ok: bool
    status: int | None
    elapsed_ms: int
    detail: str


def normalize_base_url(raw: str) -> str:
    value = raw.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be an absolute http(s) URL")
    if parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain a query string or fragment")
    return value


def endpoint(base_url: str, path: str) -> str:
    suffix = "/" + path.lstrip("/")
    if base_url.endswith(suffix):
        return base_url
    return base_url + suffix


def request_json(url: str, api_key: str | None, payload: dict[str, Any] | None, timeout: float) -> CheckResult:
    headers = {"Accept": "application/json", "User-Agent": "aifast-api-preflight/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = None
    method = "GET"
    if payload is not None:
        method = "POST"
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    started = time.monotonic()
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as response:
            body = response.read(4096).decode("utf-8", "replace")
            status = response.status
            detail = summarize_body(body)
            ok = 200 <= status < 300
    except urllib.error.HTTPError as error:
        status = error.code
        body = error.read(4096).decode("utf-8", "replace")
        detail = summarize_body(body) or error.reason
        ok = False
    except urllib.error.URLError as error:
        status = None
        detail = f"network error: {error.reason}"
        ok = False
    except TimeoutError:
        status = None
        detail = "request timed out"
        ok = False

    elapsed = round((time.monotonic() - started) * 1000)
    return CheckResult(name=url, ok=ok, status=status, elapsed_ms=elapsed, detail=detail)


def summarize_body(body: str) -> str:
    if not body.strip():
        return "empty response body"
    try:
        value = json.loads(body)
        if isinstance(value, dict):
            error = value.get("error")
            if isinstance(error, dict):
                return str(error.get("message") or error.get("type") or "API error")[:240]
            if isinstance(error, str):
                return error[:240]
            if isinstance(value.get("data"), list):
                return f"JSON response with {len(value['data'])} data items"
            return "JSON object response"
        return f"JSON {type(value).__name__} response"
    except json.JSONDecodeError:
        return "non-JSON response: " + " ".join(body.split())[:200]


def diagnose(result: CheckResult) -> str:
    if result.status in {401, 403}:
        return "authentication/permission: check Bearer format, key scope and proxy header forwarding"
    if result.status == 404:
        return "path/model routing: inspect the final URL for duplicated /v1 or endpoint paths"
    if result.status == 429:
        return "rate/quota limit: inspect response headers and use bounded exponential backoff with jitter"
    if result.status and result.status >= 500:
        return "gateway/upstream failure: retain timestamp, model ID, request ID and sanitized error body"
    if result.ok:
        return "request succeeded; test streaming/tools separately if your workload needs them"
    return "network/client failure: inspect DNS, TLS, proxy and timeout settings"


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight an OpenAI-compatible API without printing secrets")
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL"), help="API base URL, or set OPENAI_BASE_URL")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL"), help="Optional model ID for a minimal chat request")
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--dry-run", action="store_true", help="Only validate and display endpoint construction")
    args = parser.parse_args()

    if not args.base_url:
        parser.error("--base-url or OPENAI_BASE_URL is required")
    try:
        base_url = normalize_base_url(args.base_url)
    except ValueError as error:
        parser.error(str(error))

    urls = {"models": endpoint(base_url, "models"), "chat": endpoint(base_url, "chat/completions")}
    if args.dry_run:
        print(json.dumps({"base_url": base_url, "endpoints": urls}, indent=2))
        return 0

    api_key = os.getenv("OPENAI_API_KEY")
    results = [request_json(urls["models"], api_key, None, args.timeout)]
    if args.model:
        if not api_key:
            print("OPENAI_API_KEY is required for --model checks", file=sys.stderr)
            return 2
        results.append(request_json(urls["chat"], api_key, {
            "model": args.model,
            "messages": [{"role": "user", "content": "Return only: ok"}],
            "stream": False,
        }, args.timeout))

    payload = [{**asdict(result), "diagnosis": diagnose(result)} for result in results]
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in payload:
            status = item["status"] if item["status"] is not None else "n/a"
            print(f"[{ 'PASS' if item['ok'] else 'CHECK' }] {item['name']}")
            print(f"  status={status} elapsed={item['elapsed_ms']}ms")
            print(f"  detail={item['detail']}")
            print(f"  diagnosis={item['diagnosis']}")
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
