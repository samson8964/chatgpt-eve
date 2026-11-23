"""Offline tests: no ESI calls, mail, scanner or production-file writes."""
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from v4.engine import Order
from v4.celebration_crate_radar import (
    BOXES, JITA, PLEX, RANDOM_ISK, COMPLETE_GATE,
    _evaluate_contracts, _evaluate_market, _books, format_game_mail,
    latest_complete_run, rank_opportunities,
)


class Catalog:
    def volume(self, t):
        return 4 if t in BOXES else 0.0002 if t == PLEX else 1

    def classification(self, t):
        return "blueprint_type" if t == 90001 else "regular"


def order(oid, tid, location, price, remaining, *, buy):
    return Order(oid, tid, location, buy, price, remaining)


OTHER = 456789
SRC = 1049588174021


class CrateRadarTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog()
        self.haul = lambda loc, v: 0 if loc == JITA else 10_000_000 + 500 * v
        self.bids = [
            order(1, PLEX, JITA, 5_000_000, 50000, buy=True),
            order(2, OTHER, JITA, 20_000_000, 3, buy=True),
        ]

    def test_fixed_20_plex_market_value_and_freight(self):
        b = _books(self.bids + [order(3, 80240, SRC, 60_000_000, 2, buy=False)])
        rows = _evaluate_market(b, {SRC}, self.catalog, self.haul)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["guaranteed_plex"], 40)
        self.assertEqual(rows[0]["quantity"], 2)
        self.assertAlmostEqual(rows[0]["gross_isk"], 200_000_000)
        self.assertLess(rows[0]["net_profit_isk"], 80_000_000)

    def test_random_crate_is_15m_not_500plex_expected_value(self):
        b = _books([order(4, 97314, SRC, 2_000_000, 2, buy=False)])
        rows = _evaluate_market(b, {SRC}, self.catalog, self.haul)
        self.assertEqual(rows[0]["random_boxes"], 2)
        self.assertEqual(rows[0]["gross_isk"], 2 * RANDOM_ISK)
        self.assertEqual(rows[0]["guaranteed_plex"], 0)

    def test_contract_combines_plex_and_other_bid_full_contract_price_once(self):
        contract = [{"contract_id": 99, "type": "item_exchange",
                     "start_location_id": SRC, "price": 150_000_000,
                     "status": "outstanding"}]
        contents = [
            {"contract_id": 99, "type_id": 80240, "quantity": 2, "is_included": True},
            {"contract_id": 99, "type_id": OTHER, "quantity": 3, "is_included": True},
        ]
        rows = _evaluate_contracts(contract, contents, _books(self.bids),
                                   {SRC}, self.catalog, self.haul)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gross_isk"], 260_000_000)
        self.assertEqual(rows[0]["guaranteed_plex"], 40)
        self.assertEqual(rows[0]["other_credited_count"], 1)
        self.assertEqual(rows[0]["purchase_isk"], 150_000_000)

    def test_partial_other_bid_only_credits_matched_units(self):
        c = [{"contract_id": 100, "type": "item_exchange",
              "start_location_id": SRC, "price": 50_000_000}]
        contents = [
            {"contract_id": 100, "type_id": 80240, "quantity": 1,
             "is_included": True},
            {"contract_id": 100, "type_id": OTHER, "quantity": 8,
             "is_included": True},
        ]
        rows = _evaluate_contracts(c, contents, _books(self.bids),
                                   {SRC}, self.catalog, self.haul)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gross_isk"], 160_000_000)
        self.assertEqual(rows[0]["other_credited_count"], 1)
        self.assertEqual(rows[0]["other_partial_depth_types"], [OTHER])
        self.assertLess(rows[0]["haul_isk"], 10_000_000 + 500 * (4 + 8))

    def test_request_side_excludes_entire_bundle(self):
        c = [{"contract_id": 99, "type": "item_exchange",
              "start_location_id": SRC, "price": 1}]
        items = [{"contract_id": 99, "type_id": 80240,
                  "quantity": 2, "is_included": True},
                 {"contract_id": 99, "type_id": OTHER,
                  "quantity": 1, "is_included": False}]
        self.assertEqual(_evaluate_contracts(c, items, _books(self.bids),
                                              {SRC}, self.catalog, self.haul), [])

    def test_unfilled_plex_bid_cannot_estimate_guaranteed_plex(self):
        rows = _evaluate_market(_books([order(3, 80240, SRC, 1, 1, buy=False)]),
                                {SRC}, self.catalog, self.haul)
        self.assertEqual(rows, [])

    def test_unpriced_other_valued_zero_not_ask(self):
        c = [{"contract_id": 99, "type": "item_exchange",
              "start_location_id": SRC, "price": 50_000_000}]
        items = [{"contract_id": 99, "type_id": 80240, "quantity": 1,
                  "is_included": True},
                 {"contract_id": 99, "type_id": OTHER, "quantity": 100,
                  "is_included": True}]
        rows = _evaluate_contracts(c, items, _books(self.bids),
                                   {SRC}, self.catalog, self.haul)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["gross_isk"], 100_000_000)
        self.assertEqual(rows[0]["other_credited_count"], 0)
        self.assertEqual(rows[0]["unpriced_other_types"], [OTHER])

    def test_top20_total_not_twenty_per_category(self):
        c = [{"contract_id": i, "type": "item_exchange",
              "start_location_id": SRC, "price": i + 1} for i in range(30)]
        items = [{"contract_id": i, "type_id": 78889,
                  "quantity": 2, "is_included": True} for i in range(30)]
        result = rank_opportunities([], c, items, locations={SRC},
                                    catalog=self.catalog, haul_fn=self.haul)
        self.assertEqual(len(result["top20"]), 20)
        self.assertTrue(all(x["kind"] == "contract" for x in result["top20"]))
        self.assertEqual(result["top20"][0]["contract_id"], 0)

    def test_recent_complete_manifest_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "runs" / "20261123T000000Z-a"
            (p / "source").mkdir(parents=True)
            (p / "source" / "market_orders.csv.bz2").touch()
            (p / "source" / "public_contracts.tar.bz2").touch()
            (p / "manifest.json").write_text(json.dumps({
                "status": "SHADOW_RECORDED", "coverage_gate": COMPLETE_GATE,
                "source_input_integrity": "ALL_PARSED", "failed_structure_lanes": {},
                "finished_at": "2026-11-23T00:10:00Z"}), encoding="utf-8")
            actual, _ = latest_complete_run(Path(d), now=datetime(
                2026, 11, 23, 1, tzinfo=timezone.utc))
            self.assertEqual(actual, p)
            (p / "manifest.json").write_text('{"status":"FAILED"}', encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "NOT_COMPLETE"):
                latest_complete_run(Path(d), now=datetime(
                    2026, 11, 23, 1, tzinfo=timezone.utc))

    def test_game_digest_has_native_links(self):
        sample = {"top20": [
            {"kind": "contract", "contract_id": 42, "source_location": SRC,
             "included_box_types": {"80240": 1}, "net_profit_isk": 20000000,
             "roi": .1, "purchase_isk": 100000000, "haul_isk": 10000000,
             "guaranteed_plex": 20, "random_boxes": 0,
             "other_type_count": 0, "other_credited_count": 0}
        ]}
        subject, body = format_game_mail(sample)
        self.assertIn("contract:0//42", body)
        self.assertIn("PLEX 20", body)
        self.assertLess(len(body), 9000)


if __name__ == "__main__":
    unittest.main()
