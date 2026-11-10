#!/usr/bin/env python3
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "tools" / "openai_api_preflight.py"
spec = importlib.util.spec_from_file_location("preflight", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
preflight = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = preflight
spec.loader.exec_module(preflight)


class PreflightTests(unittest.TestCase):
    def test_normalize_base_url(self):
        self.assertEqual(preflight.normalize_base_url(" https://example.com/v1/ "), "https://example.com/v1")

    def test_rejects_non_absolute_url(self):
        with self.assertRaises(ValueError):
            preflight.normalize_base_url("example.com/v1")

    def test_rejects_query(self):
        with self.assertRaises(ValueError):
            preflight.normalize_base_url("https://example.com/v1?key=secret")

    def test_endpoint_does_not_duplicate_existing_suffix(self):
        self.assertEqual(
            preflight.endpoint("https://example.com/v1/models", "models"),
            "https://example.com/v1/models",
        )

    def test_endpoint_appends_path(self):
        self.assertEqual(
            preflight.endpoint("https://example.com/v1", "chat/completions"),
            "https://example.com/v1/chat/completions",
        )

    def test_summarize_api_error_without_secret_echo(self):
        secret = "audit-placeholder-key"
        body = json.dumps({"error": {"message": "invalid " + secret}})
        self.assertEqual(preflight.summarize_body(body, secret), "invalid [REDACTED]")

    def test_rejects_credentials_controls_and_insecure_remote(self):
        for url in ("https://user:password@example.com/v1", "https://example.com:99999/v1",
                    "https://exa\nmple.com", "http://example.com/v1", "http://192.168.1.1/v1"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                preflight.normalize_base_url(url, allow_insecure_localhost=True)

    def test_http_localhost_requires_explicit_flag(self):
        with self.assertRaises(ValueError):
            preflight.normalize_base_url("http://127.0.0.1:1234/v1")
        self.assertEqual(preflight.normalize_base_url("http://127.0.0.1:1234/v1", True), "http://127.0.0.1:1234/v1")

    def test_wrong_protocol_cannot_pass(self):
        for value in (None, [], {}, {"error": "bad"}, {"data": ["model"]}, {"data": [{"id": ""}]}):
            with self.subTest(value=value):
                self.assertFalse(preflight.validate_response(json.dumps(value), None)[0])
        chat = {"model": "fixture", "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]}
        self.assertTrue(preflight.validate_response(json.dumps(chat), {"model": "fixture"})[0])
        for message in ({}, {"role": "user", "content": "ok"}, {"role": "assistant", "content": ""}):
            with self.subTest(message=message):
                chat["choices"][0]["message"] = message
                self.assertFalse(preflight.validate_response(json.dumps(chat), {"model": "fixture"})[0])

    def test_invalid_key_and_timeout_do_not_send_requests(self):
        with patch.object(preflight.urllib.request, "build_opener") as opener:
            for secret, timeout in (("key\r\ninjected", 1), ("key", float("nan")), ("key", float("inf")), ("key", 0)):
                with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                    preflight.request_json("https://example.com/v1/models", secret, None, timeout)
            opener.assert_not_called()

    def test_diagnose_statuses(self):
        result = preflight.CheckResult("https://example.com/v1/models", False, 429, 10, "limited")
        self.assertIn("rate/quota", preflight.diagnose(result))


class FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.received.append({"path": self.path, "key": self.headers.get("Authorization")})
        status, body, headers = self.server.routes.get(self.path, (404, b"missing", {}))
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.do_GET()


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servers = []
        for _ in range(2):
            server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
            server.routes = {}
            server.received = []
            threading.Thread(target=server.serve_forever, daemon=True).start()
            cls.servers.append(server)

    @classmethod
    def tearDownClass(cls):
        for server in cls.servers:
            server.shutdown()
            server.server_close()

    def setUp(self):
        for server in self.servers:
            server.routes.clear()
            server.received.clear()
        self.base = f"http://127.0.0.1:{self.servers[0].server_port}"
        self.secret = "AUDIT_PLACEHOLDER_NOT_A_REAL_KEY"

    def request(self, path, payload=None):
        return preflight.request_json(self.base + path, self.secret, payload, 2, allow_insecure_localhost=True)

    def test_all_redirects_refused_without_forwarding_credentials(self):
        for status in (301, 302, 303, 307, 308):
            for payload in (None, {"model": "fixture"}):
                with self.subTest(status=status, payload=payload):
                    self.servers[0].routes['/redirect'] = (status, b"", {"Location": f"http://localhost:{self.servers[1].server_port}/sink"})
                    result = self.request('/redirect', payload)
                    self.assertFalse(result.ok)
                    self.assertEqual(result.status, status)
                    self.assertEqual(self.servers[1].received, [])

    def test_upstream_echo_redacted_before_truncation(self):
        body = json.dumps({"error": {"message": "x" * 230 + self.secret}}).encode()
        self.servers[0].routes['/echo'] = (401, body, {})
        result = self.request('/echo')
        self.assertNotIn(self.secret[:8], result.detail)
        self.assertNotIn(self.secret, json.dumps(preflight.asdict(result)))

    def test_html_empty_and_error_200_are_failures(self):
        for body in (b'<html><h1>Login</h1></html>', b'', b'{"error":{"message":"bad"}}'):
            with self.subTest(body=body):
                self.servers[0].routes['/models'] = (200, body, {})
                result = self.request('/models')
                self.assertFalse(result.ok)
                self.assertIn("协议校验未通过", preflight.diagnose(result))

    def test_large_valid_model_list_and_chat_succeed(self):
        models = {"data": [{"id": f"model-{n}"} for n in range(1000)]}
        self.servers[0].routes['/models'] = (200, json.dumps(models).encode(), {})
        self.assertTrue(self.request('/models').ok)
        chat = {"model": "fixture", "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}]}
        self.servers[0].routes['/chat/completions'] = (200, json.dumps(chat).encode(), {})
        self.assertTrue(self.request('/chat/completions', {"model": "fixture"}).ok)

    def test_oversized_response_fails(self):
        self.servers[0].routes['/large'] = (200, b'x' * (preflight.MAX_RESPONSE_BYTES + 1), {})
        result = self.request('/large')
        self.assertFalse(result.ok)
        self.assertIn("1 MiB", result.detail)

    def test_cli_text_and_json_do_not_expose_key(self):
        body = json.dumps({"error": {"message": self.secret}}).encode()
        self.servers[0].routes['/v1/models'] = (401, body, {})
        env = {**os.environ, "OPENAI_API_KEY": self.secret}
        env.pop("OPENAI_MODEL", None)
        for output in ([], ["--json"]):
            process = subprocess.run([sys.executable, '-B', str(MODULE_PATH), '--base-url', self.base + '/v1',
                                      '--allow-insecure-localhost', *output], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(process.returncode, 1)
            self.assertNotIn(self.secret, process.stdout + process.stderr)
            self.assertIn('[REDACTED]', process.stdout)


if __name__ == "__main__":
    unittest.main()
