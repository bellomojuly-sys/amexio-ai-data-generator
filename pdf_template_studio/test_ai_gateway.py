import http.client
import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from ai_gateway import PORTKEY_MODELS, chat_json


class GatewayTests(unittest.TestCase):
    @patch("ai_gateway.urllib.request.urlopen")
    def test_slugs_key_config_and_claude_json(self, send):
        fields = {"fields": [{"original": "Alice", "placeholder": "EMPLOYEE_NAME"}]}
        for slug in (*PORTKEY_MODELS, "my-custom-slug"):
            with self.subTest(slug=slug):
                body = {"choices": [{"message": {"content": "```json\n" + json.dumps(fields) + "\n```"}}]}
                send.return_value.__enter__.return_value = io.BytesIO(json.dumps(body).encode())
                self.assertEqual(chat_json([], "test-key", slug, "Portkey", "my-config"), fields)
                request = send.call_args.args[0]
                self.assertEqual(request.full_url, "https://api.portkey.ai/v1/chat/completions")
                headers = {name.lower(): value for name, value in request.header_items()}
                self.assertEqual(headers["x-portkey-api-key"], "test-key")
                self.assertEqual(headers["x-portkey-config"], "my-config")
                self.assertEqual(headers["user-agent"], "PDFTemplateStudio/1.0")
                self.assertNotIn("authorization", headers)
                payload = json.loads(request.data)
                self.assertEqual(payload["model"], slug)
                self.assertNotIn("response_format", payload)

    @patch("ai_gateway.urllib.request.urlopen")
    def test_no_config_and_empty_fields(self, send):
        send.return_value.__enter__.return_value = io.BytesIO(json.dumps(
            {"choices": [{"message": {"content": '{"fields": []}'}}]}).encode())
        self.assertEqual(chat_json([], "test", PORTKEY_MODELS[0], "Portkey"), {"fields": []})
        self.assertNotIn("x-portkey-config", {k.lower() for k, _ in send.call_args.args[0].header_items()})

    @patch("ai_gateway.urllib.request.urlopen")
    def test_bad_responses_and_auth_error(self, send):
        for content in ("not json", '{"fields": "bad"}', '{"fields": [1]}', ""):
            send.return_value.__enter__.return_value = io.BytesIO(json.dumps(
                {"choices": [{"message": {"content": content}}]}).encode())
            with self.assertRaises(ValueError):
                chat_json([], "test", PORTKEY_MODELS[0], "Portkey")
        send.side_effect = urllib.error.HTTPError("url", 401, "secret-body", {}, None)
        with self.assertRaisesRegex(ValueError, "API key was rejected"):
            chat_json([], "test", PORTKEY_MODELS[0], "Portkey")

    @patch("ai_gateway.urllib.request.urlopen")
    def test_transport_failures_have_friendly_message(self, send):
        for error in (ConnectionResetError("private details"), OSError("private details"),
                      http.client.IncompleteRead(b"private details", 100),
                      http.client.HTTPException("private details")):
            with self.subTest(error=type(error).__name__):
                send.side_effect = error
                with self.assertRaisesRegex(ValueError, "^Unable to reach Portkey. Check your connection and try again.$"):
                    chat_json([], "test-key", PORTKEY_MODELS[0], "Portkey")

    @patch("ai_gateway.urllib.request.urlopen")
    def test_non_json_success_body_has_friendly_message(self, send):
        send.return_value.__enter__.return_value = io.BytesIO(b"<html>private details</html>")
        with self.assertRaisesRegex(ValueError, "^Unable to reach Portkey. Check your connection and try again.$"):
            chat_json([], "test-key", PORTKEY_MODELS[0], "Portkey")

    @patch("ai_gateway.urllib.request.urlopen")
    def test_incomplete_response_read_has_friendly_message(self, send):
        send.return_value.__enter__.return_value.read.side_effect = http.client.IncompleteRead(b"private", 100)
        with self.assertRaisesRegex(ValueError, "^Unable to reach Portkey. Check your connection and try again.$"):
            chat_json([], "test-key", PORTKEY_MODELS[0], "Portkey")

    @patch("ai_gateway.urllib.request.urlopen")
    def test_missing_credentials_do_not_send(self, send):
        for key, slug in (("", "slug"), ("test", " ")):
            with self.assertRaises(ValueError):
                chat_json([], key, slug, "Portkey")
        send.assert_not_called()

    @patch("ai_gateway.urllib.request.urlopen")
    def test_forbidden_includes_gateway_reason_without_key(self, send):
        body = {"error": {"message": "Workspace cannot access config; key: test-secret"}}
        send.side_effect = urllib.error.HTTPError("url", 403, "Forbidden", {}, io.BytesIO(json.dumps(body).encode()))
        with self.assertRaises(ValueError) as caught:
            chat_json([], "test-secret", PORTKEY_MODELS[0], "Portkey")
        self.assertIn("Workspace cannot access config", str(caught.exception))
        self.assertNotIn("test-secret", str(caught.exception))

    @patch("ai_gateway.urllib.request.urlopen")
    def test_forbidden_does_not_expose_html(self, send):
        send.side_effect = urllib.error.HTTPError("url", 403, "Forbidden", {}, io.BytesIO(b"<html>private content</html>"))
        with self.assertRaises(ValueError) as caught:
            chat_json([], "test-key", PORTKEY_MODELS[0], "Portkey")
        self.assertNotIn("private content", str(caught.exception))
        self.assertIn("No JSON error details", str(caught.exception))

    @patch("ai_gateway.urllib.request.urlopen")
    def test_edge_error_code_is_visible(self, send):
        send.side_effect = urllib.error.HTTPError("url", 403, "Forbidden", {}, io.BytesIO(b"error code: 1010"))
        with self.assertRaisesRegex(ValueError, "error code 1010"):
            chat_json([], "test-key", PORTKEY_MODELS[0], "Portkey")


if __name__ == "__main__":
    unittest.main()
