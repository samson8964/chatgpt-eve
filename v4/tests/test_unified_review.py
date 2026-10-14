"""Only auditable snapshot profit signals enter the compact combined digest."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from v4.unified_review import yi, make_review, render, render_html


def mocked_contract():
    return {
        "run_folder":"20261014T112000Z-proof",
        "contract_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
        "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
        "source_input_integrity":"ALL_PARSED",
        "contract_proofs_audited":2,
        "research_leads_total":1,
        "research_leads":[{
            "contract_id":236977688,
            "contract_price":150000000,
            "net_profit_snapshot":59000000,
            "roi_snapshot":.25,
            "stress_profit_snapshot":48000000,
            "source_location":1053970513596,
        }]
    }


class UnifiedReviewTests(unittest.TestCase):
    def test_hundredth_of_yi_units_are_stable(self):
        self.assertEqual(yi(1000000),"0.01亿")
        self.assertEqual(yi(123456789),"1.23亿")
        self.assertEqual(yi(59000000),"0.59亿")
        self.assertEqual(yi(None),"未知")

    def test_market_proof_filtering_and_both_link_formats(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            folder=root/"runs"/"20261014T112000Z-proof"
            folder.mkdir(parents=True)
            (folder/"deep_shadow.json").write_text(json.dumps({
                "status":"SHADOW_ONLY_NO_LIVE_ALERTS",
                "market_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
                "market_execution_basis":"OPTIMIZED_MATCHED_QUANTITY_AND_VWAP",
                "market_proofs_examined":4,
                "market_potential_pairs":4}),encoding="utf-8")
            rows=[
                {"kind":"market","model_candidate":True,"status":"WATCH",
                 "source_location":1053970513596,"destination_location":60003760,
                 "valuation_location_id":60003760,
                 "valuation_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE",
                 "type_id":34,"quantity":100,"profit":62000000,"roi":.21,
                 "quantity_optimized":True,
                 "source_vwap_isk_per_unit":2000000,
                 "jita_vwap_isk_per_unit":3000000,
                 "executed_sell_cost":200000000,
                 "executed_jita_buy_gross":300000000,
                 "stress_profit":33000000,"cost":300000000,
                 "source_top5_sell":{"group_count":3,
                                    "simple_mean_isk_per_unit":2000000},
                 "jita_top5_buy":{"group_count":5,
                                   "simple_mean_isk_per_unit":8000000},
                 "reason":"LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED"},
                {"kind":"market","model_candidate":True,"status":"WATCH",
                 "source_location":1053970513596,"destination_location":60008494,
                 "valuation_location_id":60008494,
                 "valuation_basis":"SAME_LOCATION_SNAPSHOT",
                 "type_id":35,"quantity":10,"profit":990000000,"roi":.9,
                 "stress_profit":900000000,"cost":500000000,
                 "reason":"LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED"},
                {"kind":"market","model_candidate":False,"status":"WATCH",
                 "source_location":1049588174021,"destination_location":60003760,
                 "valuation_location_id":60003760,
                 "valuation_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE",
                 "type_id":36,"quantity":10,"profit":30000000,"roi":.1,
                 "stress_profit":10000000,"cost":300000000,
                 "reason":"BELOW_GATE_OR_STRESS"},
                {"kind":"market","model_candidate":True,"status":"WATCH",
                 "source_location":1049588174021,"destination_location":60003760,
                 "valuation_location_id":60003760,
                 "valuation_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE",
                 "type_id":37,"quantity":10,"profit":45000000,"roi":.3,
                 "stress_profit":-3000000,"cost":200000000,
                 "reason":"BELOW_GATE_OR_STRESS"},
            ]
            (folder/"all_proofs.jsonl").write_text(
                "".join(json.dumps(x)+"\n" for x in rows),encoding="utf-8")
            with patch("v4.unified_review.contract_review",return_value=mocked_contract()):
                output=make_review(root)
            self.assertEqual(output["market_proofs_examined"],4)
            self.assertEqual(output["market_research_leads_total"],1)
            self.assertEqual(output["market_research_leads"][0]["type_id"],34)
            self.assertFalse(output["market_research_leads"][0]["live_verified"])
            title,game=render(output,game=True)
            self.assertIn("市场1 合同1",title)
            self.assertIn("<url=contract:0//236977688><b>打开合同 236977688</b></url>",game)
            self.assertIn("<url=showinfo:34><b>查看商品 34</b></url>",game)
            self.assertIn("0.62亿",game)
            self.assertIn("0.59亿",game)
            self.assertIn("成交均 本地卖0.02亿→吉买0.03亿",game)
            self.assertIn("卖3档均0.02亿",game)
            self.assertIn("吉买5档均0.08亿",game)
            self.assertIn("待核",title)
            self.assertNotIn("Type 35",game)
            self.assertNotIn("Type 37",game)
            _,gmail=render(output,game=False)
            self.assertIn("/c/236977688",gmail)
            self.assertIn("/m/34",gmail)
            self.assertNotIn("<url=",gmail)
            _,rich = render_html(output)
            self.assertIn('/c/236977688',rich)
            self.assertIn('/m/34',rich)
            self.assertIn('<a href=',rich)
            self.assertIn('打开合同 236977688</a>',rich)
            self.assertIn('查看商品 34</a>',rich)
            self.assertIn("成交均 本地卖0.02亿→吉买0.03亿",rich)
            self.assertIn("卖3档均0.02亿",rich)
            self.assertIn("吉买5档均0.08亿",rich)
            self.assertLess(len(game),680)
            self.assertLess(len(rich),1600)
            self.assertNotIn('审核记录',game)

    def test_partial_scan_hides_all_candidates(self):
        incomplete=mocked_contract()
        incomplete["coverage_gate"]="PARTIAL_UNVERIFIED"
        incomplete["market_research_leads"]=[
            {"type_id":34,"quantity":1,"source_location":123,
             "net_profit_snapshot":50000000,"roi_snapshot":.2,
             "stress_profit_snapshot":30000000}]
        subject,body=render(incomplete,game=True)
        self.assertIn("数据不完整",body)
        self.assertNotIn("236977688",body)
        self.assertNotIn("showinfo:34",body)

    def test_mismatched_market_proof_count_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            folder=root/"runs"/"20261014T112000Z-proof"
            folder.mkdir(parents=True)
            (folder/"deep_shadow.json").write_text(json.dumps({
                "status":"SHADOW_ONLY_NO_LIVE_ALERTS",
                "market_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
                "market_execution_basis":"OPTIMIZED_MATCHED_QUANTITY_AND_VWAP",
                "market_proofs_examined":3}),encoding="utf-8")
            (folder/"all_proofs.jsonl").write_text("",encoding="utf-8")
            with patch("v4.unified_review.contract_review",return_value=mocked_contract()):
                with self.assertRaisesRegex(RuntimeError,"MARKET_PROOF_COUNT_MISMATCH"):
                    make_review(root)


if __name__=="__main__":
    unittest.main()
