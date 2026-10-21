"""Unit tests for the no-secrets BANESTAR safe HTTP/ESI diagnostic."""
from __future__ import annotations

import json
import unittest

from v4.candidate_station_diagnostic import probe, _classify

KEY = "K" * 48


class Response:
    def __init__(self, code, data=None, *, body_read_fail=False):
        self.status_code = code
        self.headers = {"Content-Type": "application/json"}
        self.data = data or {}
        self.body_read_fail = body_read_fail

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_content(self, *, chunk_size):
        if self.body_read_fail:
            raise AssertionError("success page must not be read")
        assert chunk_size <= 4096
        yield json.dumps(self.data).encode()

    @property
    def text(self):
        raise AssertionError("do not log Worker detail, tokens or order book")


class DiagnosticTests(unittest.TestCase):
    def test_wraps_underlying_esi_404_and_safe_errors_only(self):
        calls = []
        leaked = "SENSITIVE_EVE_SSO_REFRESH_TOKEN_NEVER_PRINT"
        def get(url, **kw):
            self.assertTrue(kw["stream"])
            self.assertIn("Authorization", kw["headers"])
            self.assertEqual(kw["params"]["page"], 1)
            self.assertEqual(kw["headers"]["Authorization"], "Bearer " + KEY)
            calls.append(kw["params"].copy())
            if kw["params"]["structure_id"] == 1050474463169:
                return Response(502, {
                    "error": "esi_error", "status": 404,
                    "detail": leaked,
                    "auth_url": "/auth-dc",
                })
            return Response(200, body_read_fail=True)
        result = probe(key=KEY, get=get)
        self.assertEqual(len(calls), 4)
        self.assertEqual([x["auth_profile"] for x in calls], ["cj", "dc", "cj", "dc"])
        self.assertEqual(result["checks"]["banestar_cj"]["esi_upstream_http_status"], 404)
        self.assertEqual(result["checks"]["banestar_dc"]["diagnosis"],
                         "ESI_STRUCTURE_NOT_FOUND_OR_NOT_VISIBLE")
        self.assertEqual(result["checks"]["control_cj"]["worker_http_status"], 200)
        self.assertEqual(result["checks"]["control_o4t"]["diagnosis"], "FIRST_PAGE_OK")
        self.assertNotIn(leaked, str(result))
        self.assertNotIn(KEY, str(result))
        self.assertFalse(result["orders_saved"])
        self.assertFalse(result["enrolled"])

    def test_worker_502_esi_503_is_transient_not_acl(self):
        self.assertEqual(_classify(502, 503), "ESI_TEMPORARY_UPSTREAM_FAILURE")
        self.assertEqual(_classify(502, 404), "ESI_STRUCTURE_NOT_FOUND_OR_NOT_VISIBLE")
        self.assertEqual(_classify(403, None), "ESI_STRUCTURE_ACCESS_FORBIDDEN")

    def test_auth_bypass_is_blocked_before_any_fetch(self):
        def fetch(*args, **kwargs):
            raise AssertionError("must not access network")
        result = probe(key="", get=fetch)
        self.assertEqual(result["status"], "BRIDGE_CREDENTIAL_MISSING_OR_INVALID")
        self.assertEqual(result["checks"], {})


if __name__ == "__main__":
    unittest.main()
