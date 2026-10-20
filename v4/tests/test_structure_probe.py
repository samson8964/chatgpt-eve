"""No-network minimal V4 private Worker health probe tests."""
import unittest

import requests

from v4.structure_probe import probe


class FakeResponse:
    def __init__(self, status, content_type="application/json; charset=utf-8"):
        self.status_code = status
        self.headers = {"Content-Type": content_type}

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
