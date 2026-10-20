"""No-network minimal V4 private Worker health probe tests."""
import unittest

import requests

from v4.structure_probe import probe


class FakeResponse:
    def __init__(self, status, content_type="application/json; charset=utf-8", body=None):
        self.status_code = status
        self.headers = {"Content-Type": content_type}
        self.body = body if body is not None else (
            b'{"error":"token_refresh_failed","detail":"{\"error\":\"invalid_grant\"}"}'
        )
    
    def iter_content(self, chunk_size=1024):
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i:i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class StructureProbeTests(unittest.TestCase):
    KEY = "A" * 48

    def test_three_profile_codes_no_secrets_or_body_logged(self):
        results = {"main": 403, "cj": 401, "dc": 404}
        count = []
        def get(url, **kw):
            count.append(kw["params"].copy())
            self.assertTrue(kw["stream"])
            self.assertIn("Bearer " + self.KEY, kw["headers"]["Authorization"])
            self.assertEqual(kw["params"]["page"], 1)
            return FakeResponse(results[kw["params"]["auth_profile"]])
        report = probe(key=self.KEY, get=get)
        self.assertEqual(len(count), 3)
        self.assertEqual(report["profiles"]["four_h"]["http_status"], 403)
        self.assertEqual(report["profiles"]["cj"]["http_status"], 401)
        self.assertEqual(report["profiles"]["o4t"]["http_status"], 404)
        self.assertNotIn(self.KEY, str(report))
        self.assertTrue(report["secret_displayed"] is False)
        self.assertTrue(report["orders_saved"] is False)

    def test_plain_text_401_is_worker_bridge_key_mismatch(self):
        def get(url, **kwargs):
            return FakeResponse(401, "text/plain; charset=utf-8")
        result = probe(key=self.KEY, get=get)
        self.assertTrue(all(
            row["auth_failure_layer"] == "WORKER_BRIDGE_KEY_REJECTED"
            for row in result["profiles"].values()
        ))
        self.assertNotIn(self.KEY, str(result))

    def test_json_401_is_worker_sso_refresh_layer(self):
        def get(url, **kwargs):
            return FakeResponse(401, "application/json; charset=utf-8")
        result = probe(key=self.KEY, get=get)
        self.assertTrue(all(
            row["auth_failure_layer"] == "EVE_SSO_REFRESH_FAILED"
            for row in result["profiles"].values()
        ))

    def test_worker_oauth_failure_reason_is_fixed_category_only(self):
        fixtures = [
            (b'{"error":"token_refresh_failed","detail":"no refresh token"}',
             "WORKER_REFRESH_TOKEN_MISSING"),
            (b'{"error":"token_refresh_failed","detail":"{\\"error\\":\\"invalid_client\\"}"}',
             "OAUTH_SHARED_CLIENT_CREDENTIALS_REJECTED"),
            (b'{"error":"token_refresh_failed","detail":"{\\"error\\":\\"invalid_grant\\"}"}',
             "OAUTH_SAVED_REFRESH_TOKEN_REJECTED"),
            (b'{"error":"token_refresh_failed","detail":"token request exception: private token"}',
             "OAUTH_ENDPOINT_REQUEST_EXCEPTION"),
        ]
        for body, expected in fixtures:
            with self.subTest(reason=expected):
                def get(url, **kw):
                    return FakeResponse(401, body=body)
                result = probe(key=self.KEY, get=get)
                self.assertTrue(all(
                    row["refresh_failure_reason"] == expected
                    for row in result["profiles"].values()
                ))
                self.assertNotIn("private token", str(result))
                self.assertNotIn(self.KEY, str(result))

    def test_success_never_reads_response_body(self):
        class SuccessResponse(FakeResponse):
            def iter_content(self, chunk_size=1024):
                raise AssertionError("Must never read EVE market orders")
        def get(url, **kw):
            return SuccessResponse(200)
        result = probe(key=self.KEY, get=get)
        self.assertTrue(all(
            row["http_status"] == 200 for row in result["profiles"].values()
        ))

    def test_large_error_payload_never_echoed(self):
        def get(url, **kw):
            return FakeResponse(401, body=b'SECRET-' * 2000)
        result = probe(key=self.KEY, get=get)
        self.assertTrue(all(
            row["refresh_failure_reason"] == "UNKNOWN_REFRESH_FAILURE"
            for row in result["profiles"].values()
        ))
        self.assertNotIn("SECRET", str(result))

    def test_html_401_not_misclassified(self):
        def get(url, **kwargs):
            return FakeResponse(401, "text/html")
        result = probe(key=self.KEY, get=get)
        self.assertTrue(all(
            row["auth_failure_layer"] == "UNKNOWN_401_SOURCE"
            for row in result["profiles"].values()
        ))

    def test_missing_bridge_key_never_calls_network(self):
        def network(*args, **kwargs):
            raise AssertionError("must not fetch")
        report = probe(key="", get=network)
        self.assertEqual(report["status"], "BRIDGE_CREDENTIAL_MISSING_OR_INVALID")

    def test_timeout_has_fixed_safe_category(self):
        def timeout(*args, **kwargs):
            raise requests.Timeout("URL secret: must never escape")
        report = probe(key=self.KEY, get=timeout)
        self.assertTrue(all(x["category"] == "TIMEOUT" for x in report["profiles"].values()))
        self.assertNotIn("secret:", str(report))


if __name__ == "__main__":
    unittest.main()
