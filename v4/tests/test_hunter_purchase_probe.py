"""Safe Hunter read-only procurement scan preflight tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v4.hunter_purchase_probe import (
    KNOWN, _dc_character, probe, station_catalog,
    activate_verified_hunter_mode,
)
from v4 import structure_registry as registry


class Response:
    def __init__(self, status, *, data=None, body=""):
        self.status_code = status
        self._data = data
        self.text = body

    def json(self):
        return self._data


class FakeRequests:
    def __init__(self, *, name="Arb Hunter", fail_station=None, full_pages=1):
        self.calls = []
        self.name = name
        self.fail_station = fail_station
        self.pages = full_pages

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url.endswith("/health"):
            return Response(
                200,
                body='<p>DC影子市场授权：<b>已授权</b>'
                     f' · {self.name} (2124777000) · <a href="/auth-dc">'
                     '授权/更换</a></p>',
            )
        sid = kwargs["params"]["structure_id"]
        page = kwargs["params"]["page"]
        if sid == self.fail_station:
            return Response(403)
        return Response(200, data={
            "ok": True, "structure_id": sid, "page": page,
            "pages": self.pages, "orders": [{"order_id": 90001 + page}],
        })


class HunterProbeTests(unittest.TestCase):
    KEY = "A" * 48

    def test_known_scope_excludes_jita_and_retired_four_h(self):
        stations = station_catalog()
        self.assertEqual(len(stations), 5)
        self.assertEqual(stations[-1][0], "ualx")
        self.assertEqual(stations[-1], (
            "ualx", "UALX-3 - Mothership Bellicose (BC Piggy)", 1046664001931))
        self.assertEqual(
            {x[2] for x in KNOWN},
            {1050474463169, 1049588174021, 1040804972352,
             1048663825563, 1046664001931},
        )
        self.assertNotIn(1053970513596, {x[2] for x in KNOWN})
        self.assertNotIn(60003760, {x[2] for x in KNOWN})

    def test_dc_character_only_not_general_sender_or_cj(self):
        html = (
            '<p>C-J6MT市场授权：已授权 · LadyBaBa (2124729692)</p>'
            '<p>DC影子市场授权：<b>已授权</b>'
            ' · Arb Hunter (2124777000) · <a href="/auth-dc">换</a></p>'
        )
        self.assertEqual(_dc_character(html), ("Arb Hunter", 2124777000))
        self.assertEqual(_dc_character("<p>DC影子市场授权：尚未授权</p>"),
                         (None, None))

    def test_default_five_access_checks_include_user_supplied_ualx(self):
        fake = FakeRequests()
        result = probe(expected_name="Arb Hunter", session=fake,
                       get_key=lambda: self.KEY)
        self.assertEqual(result["status"], "FIVE_FIRST_PAGES_OK")
        self.assertEqual(result["stations"]["ualx"]["status"], "PAGE1_OK")
        self.assertEqual(len(fake.calls), 6)  # health and five markets
        self.assertTrue(all(row["status"] == "PAGE1_OK"
                            for row in result["stations"].values()))
        self.assertFalse(result["purchase_enabled"])
        self.assertFalse(result["orders_saved"])
        self.assertFalse(result["production_registry_changed"])

    def test_all_five_exact_ids(self):
        fake = FakeRequests()
        result = probe(expected_name="Arb Hunter",
                       session=fake, get_key=lambda:self.KEY)
        self.assertEqual(result["status"], "FIVE_FIRST_PAGES_OK")
        self.assertEqual(len(fake.calls), 6)
        self.assertEqual(result["stations"]["ualx"]["structure_id"], 1046664001931)
        self.assertEqual(
            {call[1]["params"]["auth_profile"]
             for call in fake.calls if "params" in call[1]},
            {"dc"},
        )

    def test_complete_full_pagination_is_read_only(self):
        fake = FakeRequests(full_pages=3)
        result = probe(expected_name="Arb Hunter",
                       full=True, session=fake, get_key=lambda:self.KEY,
                       sleep=lambda _:None)
        self.assertEqual(result["status"], "FULL_PAGES_COMPLETE")
        self.assertEqual(len(fake.calls), 16)
        self.assertEqual(result["stations"]["r_arkn"]["pages_fetched"], 3)
        self.assertTrue(all(row["status"] == "COMPLETE"
                            for row in result["stations"].values()))
        self.assertFalse(result["orders_saved"])
        self.assertFalse(result["purchase_enabled"])

    def test_wrong_character_aborts_before_any_market_call(self):
        fake = FakeRequests(name="Abr Hunter")
        result = probe(expected_name="Arb Hunter", session=fake,
                       get_key=lambda:self.KEY)
        self.assertEqual(result["status"], "DC_CHARACTER_MISMATCH_OR_NOT_AUTHORIZED")
        self.assertEqual(result["authorized_character"], "Abr Hunter")
        self.assertEqual(len(fake.calls), 1)
        self.assertFalse(result["stations"])

    def test_one_denied_market_keeps_partial_failure_visible(self):
        fake = FakeRequests(fail_station=1048663825563)
        result = probe(expected_name="Arb Hunter", session=fake,
                       get_key=lambda:self.KEY)
        self.assertEqual(result["status"], "ACCESS_FAILED")
        self.assertEqual(result["stations"]["r_arkn"]["http_status"], 403)
        self.assertEqual(result["stations"]["r_arkn"]["status"], "HTTP_FAILURE")
        self.assertEqual(result["stations"]["cj"]["status"], "PAGE1_OK")
        self.assertNotIn(self.KEY, json.dumps(result))

    def test_exact_registry_consistency_and_no_duplicate_ids(self):
        actual = [(lane, sid, profile) for lane, label, sid, profile
                  in registry.HUNTER_FIVE_LANES]
        self.assertEqual(
            [(lane, sid) for lane, _, sid in KNOWN],
            [(lane, sid) for lane, sid, _ in actual])
        self.assertEqual({profile for _, _, profile in actual}, {"dc"})
        self.assertEqual(len({sid for _, sid, _ in actual}), 5)
        self.assertFalse("four_h" in {lane for lane, _, _ in actual})

    def test_full_success_can_atomically_enable_five_lane_mode(self):
        fake = FakeRequests(full_pages=2)
        result = probe(expected_name="Arb Hunter", full=True, session=fake,
                       get_key=lambda:self.KEY, sleep=lambda _:None)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "hunter-five-station.enabled"
            with patch.object(registry, "HUNTER_ENABLE_FILE", p):
                self.assertFalse(registry.hunter_enabled())
                activation = activate_verified_hunter_mode(result, path=p)
                self.assertTrue(activation["enabled"])
                self.assertFalse(activation["formal_opportunity_push_changed"])
                self.assertEqual(activation["orders_purchased"], 0)
                self.assertEqual(p.read_text("utf-8"),
                                 registry.HUNTER_ENABLE_CONTENT)
                self.assertTrue(registry.hunter_enabled())

    def test_failed_or_partial_scope_does_not_write_enable_marker(self):
        fake = FakeRequests(fail_station=1048663825563)
        result = probe(expected_name="Arb Hunter", full=True, session=fake,
                       get_key=lambda:self.KEY, sleep=lambda _:None)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "hunter-five-station.enabled"
            with self.assertRaisesRegex(ValueError, "VERIFICATION_NOT_COMPLETE"):
                activate_verified_hunter_mode(result, path=p)
            self.assertFalse(p.exists())
            fake_success = FakeRequests(full_pages=1)
            page1 = probe(expected_name="Arb Hunter", session=fake_success,
                          get_key=lambda:self.KEY)
            with self.assertRaises(ValueError):
                activate_verified_hunter_mode(page1, path=p)
            self.assertFalse(p.exists())

    def test_wrong_hunter_spelling_never_activates(self):
        fake = FakeRequests(name="Abr Hunter", full_pages=1)
        result = probe(expected_name="Arb Hunter", full=True, session=fake,
                       get_key=lambda:self.KEY, sleep=lambda _:None)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "hunter-five-station.enabled"
            with self.assertRaises(ValueError):
                activate_verified_hunter_mode(result, path=p)
            self.assertFalse(p.exists())



if __name__ == "__main__":
    unittest.main()
