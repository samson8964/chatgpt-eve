"""No-network regression for HY-RWO 1049633275448 gated sixth market lane."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from v4 import structure_registry as registry
from v4.hy_rwo_enrollment import (
    AUTH_PROFILE, EXPECTED_CHARACTER_ID, STATION_ID, STATION_LANE,
    activate, probe,
)


class Response:
    def __init__(self, code=200, payload=None, text=""):
        self.status_code = code
        self._payload = payload
        self.text = text
        self.headers = {"Content-Type": "application/json"}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("test non-secret HTTP error")


def order(n=1, station=STATION_ID):
    return {"order_id": n, "location_id": station, "type_id": 34,
            "is_buy_order": False, "price": 100.5, "volume_remain": 1}


class FakeSession:
    def __init__(self, name="Arb Hunter", ident=EXPECTED_CHARACTER_ID,
                 page_count=2, bad_page=None, status=200, location=STATION_ID):
        self.name, self.ident = name, ident
        self.page_count, self.bad_page = page_count, bad_page
        self.status, self.location = status, location
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url.endswith("/health"):
            return Response(text=(
                '<p>DC影子市场授权：<b>已授权</b> · '
                f'{self.name} ({self.ident}) · '
                '<a href="/auth-dc">授权/更换</a></p>'
            ))
        page = kwargs["params"]["page"]
        if self.bad_page == page:
            return Response(403)
        return Response(self.status, payload={
            "ok": True, "structure_id": STATION_ID, "page": page,
            "pages": self.page_count,
            "orders": [order(page, self.location)]
        })


class HyRwoTests(unittest.TestCase):
    KEY = "Z" * 48

    def test_exact_user_station_and_dc_profile(self):
        self.assertEqual(registry.HY_RWO_LANE,
                         ("hy_rwo", "HY-RWO", 1049633275448, "dc"))
        self.assertEqual(AUTH_PROFILE, "dc")
        self.assertNotIn(STATION_LANE,
                         {lane for lane, _, _, _ in registry.HUNTER_FIVE_LANES})
        self.assertNotIn("four_h", {lane for lane, _, _, _ in
                                   registry.HUNTER_FIVE_LANES})

    def test_page1_only_no_activation_or_secret_leak(self):
        client = FakeSession()
        out = probe(session=client, get_key=lambda:self.KEY)
        self.assertEqual(out["status"], "PAGE1_OK")
        self.assertFalse(out["full_pagination_verified"])
        self.assertFalse(out["orders_saved"])
        self.assertFalse(out["email_sent"])
        self.assertFalse(out["purchases_made"])
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(client.calls[1][1]["params"],
                         {"structure_id": STATION_ID, "auth_profile": "dc", "page": 1})
        self.assertNotIn(self.KEY, str(out))

    def test_full_pagination_pass_and_opt_in_only_after_five(self):
        client = FakeSession()
        out = probe(full=True, session=client, get_key=lambda:self.KEY,
                    sleep=lambda _:None, jitter=lambda:0)
        self.assertEqual(out["status"], "FULL_PAGES_VERIFIED")
        self.assertEqual(out["orders_count"], 2)
        self.assertEqual(out["pages_verified"], 2)
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            marker = base / "hunter-five-station.enabled"
            hy_marker = base / "hunter-hy-rwo.enabled"
            with patch.object(registry, "HUNTER_ENABLE_FILE", marker), \
                 patch.object(registry, "HY_RWO_ENABLE_FILE", hy_marker):
                self.assertFalse(registry.hunter_enabled())
                with self.assertRaisesRegex(ValueError, "FIVE_MODE"):
                    activate(out)
                self.assertFalse(hy_marker.exists())
                marker.write_text(registry.HUNTER_ENABLE_CONTENT, encoding="utf-8")
                self.assertTrue(registry.hunter_enabled())
                self.assertFalse(registry.hy_rwo_enabled())
                enabled = activate(out)
                self.assertTrue(enabled["enabled"])
                self.assertTrue(registry.hy_rwo_enabled())
                self.assertEqual(hy_marker.read_text("utf-8"),
                                 registry.HY_RWO_ENABLE_CONTENT)
                self.assertFalse(enabled["formal_alerts_changed"])
                self.assertEqual(enabled["orders_purchased"], 0)

    def test_identity_typo_or_wrong_character_id_fails_before_market(self):
        for name,ident in (("Abr Hunter", EXPECTED_CHARACTER_ID),
                           ("Arb Hunter", EXPECTED_CHARACTER_ID+1)):
            client = FakeSession(name=name, ident=ident)
            out = probe(full=True, session=client, get_key=lambda:self.KEY)
            self.assertEqual(out["status"], "DC_CHARACTER_MISMATCH")
            self.assertEqual(len(client.calls), 1)

    def test_partial_full_book_denied_and_corrupt_orders_never_activate(self):
        denied = FakeSession(bad_page=2)
        out = probe(full=True, session=denied, get_key=lambda:self.KEY,
                    sleep=lambda _:None, jitter=lambda:0)
        self.assertEqual(out["status"], "FULL_READ_INCOMPLETE")
        self.assertEqual(out["market_health"]["http_status"], 403)

        wrong_location = FakeSession(location=123)
        corrupt = probe(full=True, session=wrong_location,
                        get_key=lambda:self.KEY,
                        sleep=lambda _:None, jitter=lambda:0)
        self.assertEqual(corrupt["status"], "FULL_READ_ORDER_INTEGRITY_FAILED")
        self.assertFalse(corrupt["orders_saved"])

    def test_bad_or_wrong_marker_is_not_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base = root / "hunter-five-station.enabled"
            hy = root / "hunter-hy-rwo.enabled"
            with patch.object(registry, "HUNTER_ENABLE_FILE", base), \
                 patch.object(registry, "HY_RWO_ENABLE_FILE", hy):
                hy.write_text(registry.HY_RWO_ENABLE_CONTENT, encoding="utf-8")
                self.assertFalse(registry.hy_rwo_enabled())
                base.write_text(registry.HUNTER_ENABLE_CONTENT, encoding="utf-8")
                self.assertTrue(registry.hy_rwo_enabled())
                hy.write_text("wrong ID", encoding="utf-8")
                self.assertFalse(registry.hy_rwo_enabled())


if __name__ == "__main__":
    unittest.main()
