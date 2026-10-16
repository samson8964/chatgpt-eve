"""Read-only saved-report coverage audit fixtures. No network and no pandas."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v4.coverage_audit import audit_run, history


def sample(root: Path, name: str, *,
           market_count=1500, public_active=1498, cj_pages_fetched=3,
           status="SHADOW_RECORDED"):
    folder=root/"runs"/name
    folder.mkdir(parents=True)
    (folder/"manifest.json").write_text(json.dumps({
        "status":status,"coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
        "started_at":"2026-10-16T00:23:01Z","finished_at":"2026-10-16T00:25:00Z"
    }))
    (folder/"full_market_report.json").write_text(json.dumps({
        "overall":"CENSUS_COMPLETE_PROOFS_NOT_READY",
        "market":{
            "market_raw_rows":market_count,"sell_order_rows":900,
            "buy_order_rows":598,"market_locations":700,
            "market_types":210,"source_location_type_pairs":2000,
            "optimistic_initial_candidates":125
        },
        "contracts":{"contract_rows_total":14000,"contract_item_rows_total":51000}
    }))
    lanes={
        "four_h":{"status":"COMPLETE","orders":110,"pages":2,"pages_fetched":2},
        "cj":{"status":"COMPLETE","orders":220,"pages":3,"pages_fetched":cj_pages_fetched},
        "o4t":{"status":"COMPLETE","orders":30,"pages":1,"pages_fetched":1}
    }
    market_station_census={
        "4-H":{"active_sell_orders":60,"active_buy_orders":50,
               "active_sell_type_ids":50,"sell_types_with_jita_buy":35,
               "sell_types_without_jita_buy":15,
               "sell_types_best_price_crossed":20,
               "sell_types_optimistic_gate_passed":3},
        "C-J":{"active_sell_orders":120,"active_buy_orders":100,
               "active_sell_type_ids":70,"sell_types_with_jita_buy":50,
               "sell_types_without_jita_buy":20,
               "sell_types_best_price_crossed":40,
               "sell_types_optimistic_gate_passed":9},
        "O4T":{"active_sell_orders":20,"active_buy_orders":10,
               "active_sell_type_ids":8,"sell_types_with_jita_buy":5,
               "sell_types_without_jita_buy":3,
               "sell_types_best_price_crossed":2,
               "sell_types_optimistic_gate_passed":1}
    }
    (folder/"deep_shadow.json").write_text(json.dumps({
        "source_input_integrity":"ALL_PARSED",
        "public_market_rows_raw":market_count,
        "public_market_orders":public_active,
        "zero_remaining_public_orders":2,
        "invalid_public_orders":0,
        "structure_market_rows_raw":360,
        "authorized_structure_orders":360,
        "zero_remaining_structure_orders":0,
        "invalid_structure_orders":0,
        "structure_health":lanes,
        "market_station_sell_census":market_station_census,
        "verified_approved_locations":6,
        "market_potential_pairs":13,
        "market_proofs_examined":13,
        "contract_approved_locations_examined":9000,
        "npc_contracts_approved_for_deep_analysis":8500
    }))
    return folder


class CoverageAuditTests(unittest.TestCase):
    def test_exact_book_count_and_funnel(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            sample(root,"20261016T002300Z-abc")
            a=history(root,last=10)
            self.assertEqual(a["examined_completed_runs"],1)
            row=a["runs"][0]
            self.assertTrue(row["local_book_coverage_checks_pass"])
            self.assertTrue(all(v is True for v in row["quality_checks"].values()))
            self.assertEqual(row["public_market_sell_station_item_pairs"],2000)
            self.assertEqual(row["public_market_global_best_bid_optimistic_pairs"],125)
            self.assertEqual(row["market_jita_exit_gross_gate_pairs"],13)
            self.assertEqual(row["stations"]["C-J"]["raw_orders"],220)
            self.assertEqual(row["stations"]["C-J"]["sell_types_with_jita_buy"],50)
            self.assertEqual(row["contract_source_and_cash_exchange_approved"],9000)

    def test_missing_page_cannot_report_local_coverage_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=sample(root,"20261016T002300Z-abc",cj_pages_fetched=2)
            a=audit_run(p)
            self.assertFalse(a["local_book_coverage_checks_pass"])
            self.assertFalse(a["quality_checks"]["all_three_structure_page_ranges_complete"])
            self.assertFalse(a["stations"]["C-J"]["pages_complete"])

    def test_missing_rows_and_partial_order_counts_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=sample(root,"20261016T002300Z-abc",market_count=1500,public_active=1478)
            a=audit_run(p)
            self.assertFalse(a["local_book_coverage_checks_pass"])
            self.assertFalse(a["quality_checks"]["public_order_accounting_exact"])

    def test_completed_only_latest_first(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            sample(root,"20261015T002300Z-old")
            sample(root,"20261016T002300Z-new",status="FAILED")
            sample(root,"20261016T012300Z-latest")
            a=history(root,last=2)
            self.assertEqual([x["run"] for x in a["runs"]],
                 ["20261016T012300Z-latest","20261015T002300Z-old"])


if __name__=="__main__":
    unittest.main()
