"""First-found ordering and ten-per-category mail regressions."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v4.discovery_history import (
    market_key, contract_key, first_seen, order_by_discovery, INDEX
)
from v4.unified_review import make_review, render, render_html, MAX_EACH

JITA = 60003760
SOURCE = 1049588174021
OLD = "20261015T042302Z-old"
NEW = "20261015T062302Z-new"


def market(tid, *, profit=60_000_000, quantity=1):
    return {
        "kind":"market", "status":"WATCH", "model_candidate":True,
        "source_location": SOURCE, "destination_location": JITA,
        "valuation_location_id":JITA,
        "valuation_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE",
        "type_id": tid, "quantity":quantity, "profit":profit,
        "roi":.15, "stress_profit":55_000_000, "cost":100_000_000,
        "quantity_optimized":True, "source_vwap_isk_per_unit":10_000_000,
        "jita_vwap_isk_per_unit":15_000_000,
        "executed_sell_cost":10_000_000*quantity,
        "executed_jita_buy_gross":15_000_000*quantity,
    }


def contract(cid):
    return {
        "kind":"contract","contract_id":cid, "source_location":JITA,
        "destination_location":JITA,"valuation_location_id":JITA,
        "valuation_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE",
        "status":"WATCH", "reason":"LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED",
        "net_profit":80_000_000,"roi":.2,"stress_profit":60_000_000,
        "cost":100_000_000,"included_items":{"34":3},
    }


def make_run(root, name, rows):
    folder = root / "runs" / name
    folder.mkdir(parents=True)
    (folder/"manifest.json").write_text(json.dumps({"status":"SHADOW_RECORDED"}),encoding="utf-8")
    (folder/"all_proofs.jsonl").write_text(
        "".join(json.dumps(x)+"\n" for x in rows),encoding="utf-8")
    return folder


class DiscoveryMailTests(unittest.TestCase):
    def test_first_seen_is_stable_when_old_item_repeated_or_quantity_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            make_run(root, OLD, [market(34),contract(2000)])
            make_run(root, NEW, [
                market(34,quantity=7), market(35),contract(2000),contract(2001)])
            seen=first_seen(root, NEW)
            self.assertLess(seen[market_key(market(34))],
                            seen[market_key(market(35))])
            self.assertLess(seen[contract_key(contract(2000))],
                            seen[contract_key(contract(2001))])
            self.assertEqual(first_seen(root, NEW),seen)
            self.assertTrue((root/INDEX).is_file())
            ordered=order_by_discovery([
                {"source_location":SOURCE,"type_id":34,"net_profit_snapshot":900_000_000},
                {"source_location":SOURCE,"type_id":35,"net_profit_snapshot":60_000_000}
            ],kind="market",seen=seen,fallback_run=NEW)
            self.assertEqual([x["type_id"] for x in ordered],[35,34])

    def test_10_newest_market_and_contracts_not_profit_pretruncated(self):
        self.assertEqual(MAX_EACH,10)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            make_run(root, OLD,[market(34,profit=900_000_000),contract(2000)])
            current=[market(t) for t in range(34,45)]
            folder=make_run(root, NEW,current+[contract(cid) for cid in range(2000,2011)])
            (folder/"deep_shadow.json").write_text(json.dumps({
                "status":"SHADOW_ONLY_NO_LIVE_ALERTS",
                "market_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
                "market_execution_basis":"OPTIMIZED_MATCHED_QUANTITY_AND_VWAP",
                "market_proofs_examined":11,
                "market_potential_pairs":11
            }),encoding="utf-8")
            def contract_fixture(root_arg, *, limit):
                self.assertIsNone(limit)
                return {
                    "run_folder":NEW,
                    "contract_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
                    "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                    "source_input_integrity":"ALL_PARSED",
                    "contract_proofs_audited":11,
                    "research_leads_total":11,
                    "research_leads":[{
                        "contract_id":cid,
                        "net_profit_snapshot":900_000_000 if cid==2000 else 60_000_000,
                        "roi_snapshot":.15,"contract_price":100_000_000,
                        "source_location":JITA,
                    } for cid in range(2000,2011)],
                }
            with patch("v4.unified_review.contract_review",side_effect=contract_fixture):
                review=make_review(root)
            m=review["market_research_leads"]
            c=review["contract_research_leads"]
            self.assertEqual(len(m),10)
            self.assertEqual(len(c),10)
            self.assertEqual(len(review["research_leads"]),10)
            self.assertEqual([x["contract_id"] for x in review["research_leads"]],
                             [x["contract_id"] for x in c])
            self.assertEqual(review["market_research_leads_total"],11)
            self.assertEqual(review["contract_research_leads_total"],11)
            self.assertNotIn(34,[x["type_id"] for x in m])
            self.assertNotIn(2000,[x["contract_id"] for x in c])
            self.assertEqual({x["type_id"] for x in m},set(range(35,45)))
            self.assertEqual({x["contract_id"] for x in c},set(range(2001,2011)))
            for game in (False,True):
                subject,body=render(review,game=game)
                self.assertIn("市场10 合同10",subject)
                self.assertIn("首见10-15 14:23",body)
                self.assertNotIn("商品 34",body)
                self.assertNotIn("合同 2000 ",body)
            _,html=render_html(review)
            self.assertIn("首见10-15 14:23",html)

    def test_nonqualified_proofs_do_not_backdate_first_seen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            older=market(34)
            older["model_candidate"]=False
            make_run(root, OLD,[older,{"kind":"contract","contract_id":2000,
                                      "reason":"BELOW_GATE_OR_STRESS",
                                      "net_profit":-1}])
            make_run(root, NEW,[market(34),contract(2000)])
            seen=first_seen(root,NEW)
            self.assertEqual(seen[market_key(market(34))],
                             "2026-10-15T06:23:02Z")
            self.assertEqual(seen[contract_key(contract(2000))],
                             "2026-10-15T06:23:02Z")

if __name__ == "__main__":
    unittest.main()
