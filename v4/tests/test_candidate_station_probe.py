"""Offline-only tests for read-only S0B station enrollment preflight."""
import unittest

import requests

from v4.candidate_station_probe import STATION_ID, probe


class FakeResponse:
    def __init__(self, status):
        self.status_code = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    @property
    def text(self):
        raise AssertionError("Never access response bodies")

    @property
    def content(self):
        raise AssertionError("Never download orders")

    def iter_content(self, *args, **kwargs):
        raise AssertionError("Never stream orders")


class CandidateProbeTests(unittest.TestCase):
    SECRET = "K" * 48

    def test_probes_three_existing_profiles_not_production(self):
        statuses = {"main": 200, "cj": 403, "dc": 502}
        seen = []

        def fetch(url, **kwargs):
            self.assertTrue(kwargs["stream"])
            self.assertEqual(kwargs["params"]["structure_id"], STATION_ID)
            self.assertEqual(kwargs["params"]["page"], 1)
            self.assertEqual(kwargs["headers"]["Authorization"], "Bearer " + self.SECRET)
            profile = kwargs["params"]["auth_profile"]
            seen.append(profile)
            return FakeResponse(statuses[profile])

        result = probe(key=self.SECRET, get=fetch)
        self.assertEqual(seen, ["main", "cj", "dc"])
        self.assertEqual(result["status"], "CANDIDATE_ACCESS_PROBED_NOT_ENROLLED")
        self.assertEqual(result["profiles"]["main"]["access_result"], "FIRST_PAGE_ACCESS_OK")
        self.assertEqual(result["profiles"]["cj"]["access_result"], "NO_MARKET_ACCESS_FOR_CHARACTER")
        self.assertEqual(result["profiles"]["dc"]["access_result"], "UPSTREAM_ESI_ERROR_CHECK_SSO_OR_STRUCTURE")
        self.assertFalse(result["enrolled"])
        self.assertFalse(result["orders_saved"])
        self.assertTrue(result["production_push_unchanged"])
        self.assertNotIn(self.SECRET, str(result))

    def test_missing_secret_blocks_all_requests(self):
        def should_not_fetch(*args, **kwargs):
            raise AssertionError("network must not be used")
        result = probe(key="", get=should_not_fetch)
        self.assertEqual(result["status"], "BRIDGE_CREDENTIAL_MISSING_OR_INVALID")

    def test_timeout_does_not_print_exception_or_credentials(self):
        def fetch(*args, **kwargs):
            raise requests.Timeout("private bearer MUST_NOT_LEAK")
        result = probe(key=self.SECRET, get=fetch)
        self.assertTrue(all(v["access_result"] == "TIMEOUT" for v in result["profiles"].values()))
        self.assertNotIn("MUST_NOT_LEAK", str(result))


if __name__ == "__main__":
    unittest.main()
