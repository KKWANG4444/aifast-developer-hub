#!/usr/bin/env python3
import importlib.util
import pathlib
import sys
import unittest

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
        body = '{"error":{"type":"invalid_request_error","message":"bad model"}}'
        self.assertEqual(preflight.summarize_body(body), "bad model")

    def test_diagnose_statuses(self):
        result = preflight.CheckResult("https://example.com/v1/models", False, 429, 10, "limited")
        self.assertIn("rate/quota", preflight.diagnose(result))


if __name__ == "__main__":
    unittest.main()
