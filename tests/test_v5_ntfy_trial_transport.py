# -*- coding: utf-8 -*-
"""Safe, offline tests for the ConoHa ntfy trial transport."""
import unittest
from urllib.error import HTTPError, URLError

from v5.ntfy_trial_transport import URL, publish, validate_message


class FakeResponse:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class TrialNtfyTransportTests(unittest.TestCase):
    def test_preview_never_sends(self):
        def forbidden(*_args, **_kwargs):
            self.fail("preview must not use network")
        result = publish("V5 preview", http_open=forbidden)
        self.assertEqual(result, "DRY_RUN")

    def test_explicit_authorization_is_required(self):
        with self.assertRaisesRegex(ValueError, "V5_NTFY_SEND"):
            publish("hi", allow_send=True, environ={})

    def test_password_must_be_configured(self):
        with self.assertRaisesRegex(ValueError, "credential"):
            publish("hi", allow_send=True, environ={"V5_NTFY_SEND": "YES"})

    def test_single_authenticated_local_post(self):
        calls = []

        def fake_open(req, timeout):
            calls.append((req, timeout))
            return FakeResponse()

        result = publish(
            "日本語の試験通知",
            title="V5 Test",
            allow_send=True,
            environ={"V5_NTFY_SEND": "YES", "V5_NTFY_PUBLISHER_PASSWORD": "mock-secret"},
            http_open=fake_open,
        )
        self.assertEqual(result, "SENT")
        self.assertEqual(len(calls), 1)
        req, timeout = calls[0]
        self.assertEqual(req.full_url, URL)
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.data, "日本語の試験通知".encode("utf-8"))
        self.assertEqual(req.get_header("Title"), "V5 Test")
        self.assertTrue(req.get_header("Authorization").startswith("Basic "))
        self.assertEqual(timeout, 15)

    def test_invalid_body_and_title_fail_closed(self):
        for msg, title in (("", "OK"), ("x" * 3501, "OK"), ("hi", "bad\nheader"), ("hi", "日本語")):
            with self.subTest(title=title):
                with self.assertRaises(ValueError):
                    validate_message(msg, title)

    def test_http_error_is_sanitized(self):
        def fake_open(_req, timeout):
            raise HTTPError(URL, 429, "blocked", hdrs=None, fp=None)
        with self.assertRaisesRegex(RuntimeError, "^NTFY_HTTP_ERROR_429$"):
            publish("hi", allow_send=True, environ={
                "V5_NTFY_SEND": "YES",
                "V5_NTFY_PUBLISHER_PASSWORD": "do-not-print",
            }, http_open=fake_open)

    def test_network_error_is_sanitized(self):
        def fake_open(_req, timeout):
            raise URLError("private data must not be logged")
        with self.assertRaisesRegex(RuntimeError, "^NTFY_NETWORK_ERROR$"):
            publish("hi", allow_send=True, environ={
                "V5_NTFY_SEND": "YES",
                "V5_NTFY_PUBLISHER_PASSWORD": "do-not-print",
            }, http_open=fake_open)


if __name__ == "__main__":
    unittest.main()
