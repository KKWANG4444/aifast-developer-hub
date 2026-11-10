#!/usr/bin/env python3
"""校验 OpenAI 兼容接口路径与响应，阻止重定向并在输出前移除密钥。"""

from __future__ import annotations

import argparse
import json
import math
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse

MAX_RESPONSE_BYTES = 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def redact(value: str, api_key: str | None = None) -> str:
    text = str(value)
    for secret in (api_key, api_key.strip() if api_key else None):
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return " ".join(text.split())


@dataclass
class CheckResult:
    name: str
    ok: bool
    status: int | None
    elapsed_ms: int
    detail: str


def normalize_base_url(raw: str, allow_insecure_localhost: bool = False) -> str:
    value = raw.strip().rstrip("/")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Base URL 不能包含控制字符")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL must be an absolute http(s) URL")
    if not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError("Base URL 不能包含账号或密码")
    try:
        port = parsed.port
    except ValueError:
        raise ValueError("Base URL 端口无效") from None
    if port == 0:
        raise ValueError("Base URL 端口无效")
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (allow_insecure_localhost and local):
        raise ValueError("公开目标必须使用 HTTPS；本机 HTTP 测试需显式启用")
    if parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain a query string or fragment")
    return value


def endpoint(base_url: str, path: str) -> str:
    suffix = "/" + path.lstrip("/")
    if base_url.endswith(suffix):
        return base_url
    return base_url + suffix


def validate_response(body: str, payload: dict[str, Any] | None) -> tuple[bool, str]:
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return False, "响应不是有效 JSON"
    if not isinstance(value, dict) or "error" in value:
        return False, "响应不是 API 成功对象"
    if payload is None:
        models = value.get("data")
        valid = isinstance(models, list) and all(
            isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"].strip()
            for item in models
        )
        return bool(valid), f"模型列表结构通过，共 {len(models)} 项" if valid else "缺少有效的模型列表 data"
    choices = value.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return False, "缺少 Chat Completions choices"
    message = choices[0].get("message")
    valid = (isinstance(value.get("model"), str) and bool(value["model"].strip())
             and isinstance(message, dict) and message.get("role") == "assistant"
             and isinstance(message.get("content"), str) and bool(message["content"].strip())
             and isinstance(choices[0].get("finish_reason"), str) and bool(choices[0]["finish_reason"]))
    return bool(valid), "Chat Completions 文本响应结构通过" if valid else "缺少有效的模型、助手文本或结束原因"


def read_body(response) -> str:
    data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise ValueError("响应超过 1 MiB 限制")
    return data.decode("utf-8", "replace")


def request_json(url: str, api_key: str | None, payload: dict[str, Any] | None, timeout: float,
                 *, allow_insecure_localhost: bool = False) -> CheckResult:
    url = normalize_base_url(url, allow_insecure_localhost)
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError("超时必须是 0 到 120 秒之间的有限正数")
    if api_key and (not api_key.strip() or any(ord(char) < 32 or ord(char) > 126 for char in api_key)):
        raise ValueError("API Key 格式无效")
    headers = {"Accept": "application/json", "User-Agent": "aifast-api-preflight/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key.strip()}"
    data = None
    method = "GET"
    if payload is not None:
        method = "POST"
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")

    started = time.monotonic()
    status = None
    ok = False
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        with opener.open(req, timeout=timeout) as response:
            body = read_body(response)
            status = response.status
            valid, detail = validate_response(body, payload)
            ok = 200 <= status < 300 and valid
    except urllib.error.HTTPError as error:
        status = error.code
        try:
            detail = "已拒绝重定向，未向新地址发送密钥" if 300 <= status < 400 else summarize_body(read_body(error), api_key)
        except (ValueError, OSError):
            detail = "无法读取完整错误响应"
        finally:
            error.close()
    except urllib.error.URLError as error:
        status = None
        detail = f"network error: {error.reason}"
        ok = False
    except TimeoutError:
        status = None
        detail = "request timed out"
        ok = False
    except (ValueError, OSError) as error:
        detail = f"请求失败: {redact(str(error), api_key)}"

    elapsed = round((time.monotonic() - started) * 1000)
    return CheckResult(name=redact(url, api_key), ok=ok, status=status, elapsed_ms=elapsed,
                       detail=redact(detail, api_key)[:240])


def summarize_body(body: str, api_key: str | None = None) -> str:
    if not body.strip():
        return "empty response body"
    try:
        value = json.loads(body)
        if isinstance(value, dict):
            error = value.get("error")
            if isinstance(error, dict):
                return redact(error.get("message") or error.get("type") or "API error", api_key)[:240]
            if isinstance(error, str):
                return redact(error, api_key)[:240]
            if isinstance(value.get("data"), list):
                return f"JSON response with {len(value['data'])} data items"
            return "JSON object response"
        return f"JSON {type(value).__name__} response"
    except json.JSONDecodeError:
        return "non-JSON response"


def diagnose(result: CheckResult) -> str:
    if result.status and 300 <= result.status < 400:
        return "重定向被拒绝：请核验最终 HTTPS API 地址后重新配置"
    if result.status and 200 <= result.status < 300 and not result.ok:
        return "协议校验未通过：检查是否返回 HTML、空响应、错误对象或错误端点"
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
    parser.add_argument("--allow-insecure-localhost", action="store_true", help="仅允许本机模拟服务使用 HTTP")
    args = parser.parse_args()

    if not args.base_url:
        parser.error("--base-url or OPENAI_BASE_URL is required")
    try:
        base_url = normalize_base_url(args.base_url, args.allow_insecure_localhost)
        if not math.isfinite(args.timeout) or not 0 < args.timeout <= 120:
            raise ValueError("超时必须是 0 到 120 秒之间的有限正数")
    except ValueError as error:
        parser.error(str(error))

    urls = {"models": endpoint(base_url, "models"), "chat": endpoint(base_url, "chat/completions")}
    if args.dry_run:
        print(json.dumps({"base_url": base_url, "endpoints": urls}, indent=2))
        return 0

    api_key = os.getenv("OPENAI_API_KEY")
    if args.model and not api_key:
        print("OPENAI_API_KEY is required for --model checks", file=sys.stderr)
        return 2
    try:
        results = [request_json(urls["models"], api_key, None, args.timeout,
                                allow_insecure_localhost=args.allow_insecure_localhost)]
        if args.model:
            results.append(request_json(urls["chat"], api_key, {
                "model": args.model,
                "messages": [{"role": "user", "content": "Return only: ok"}],
                "max_tokens": 64,
                "stream": False,
            }, args.timeout, allow_insecure_localhost=args.allow_insecure_localhost))
    except ValueError as error:
        parser.error(redact(str(error), api_key))

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
