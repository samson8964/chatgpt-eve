"""V4 market/contract cargo volume audit and both Gmail/EVE mail renderers."""
from __future__ import annotations

import math
import unittest

from v4.mail_volume import (
    contract_label, contract_volume, credited_volume_breakdown, format_m3,
    market_label, market_volume
)
from v4.unified_review import render, render_html


class MailVolumeTests(unittest.TestCase):
    def test_market_optimized_quantity_not_entire_sell_book(self):
        proof={"volume_m3":1250.5,"cargo_volume_m3":3751.5}
        measured=market_volume(proof,3)
        self.assertEqual(measured["unit_volume_m3"],1250.5)
        self.assertEqual(measured["transport_volume_m3"],3751.5)
        self.assertEqual(market_label(measured),
                         "体积 单件1,250.5 m³ / 合计3,751.5 m³")
        self.assertIsNone(market_volume(proof,4)["transport_volume_m3"])

    def test_contract_mixed_items_credit_only_sold_subset(self):
        proof={
            "cargo_volume_m3":20.5,
            "included_volumes":{"34":.01,"35":10.0,"36":500.0,"37":None}
        }
        included={"34":150,"35":20,"36":1,"37":1}
        credited={"34":50,"35":2}
        result=contract_volume(proof,included,credited)
        self.assertEqual(result["credited_transport_volume_m3"],20.5)
        self.assertIsNone(result["whole_contract_volume_m3"])
        self.assertEqual(result["whole_contract_known_minimum_m3"],701.5)
        self.assertEqual(result["whole_contract_missing_volume_types"],1)
        self.assertIn("计价货物20.5 m³",contract_label(result))
        self.assertIn("至少701.5 m³",contract_label(result))
        items=credited_volume_breakdown(result)
        self.assertIn("Type 34×50 单件0.01 m³ 小计0.5 m³",items)
        self.assertIn("Type 35×2 单件10 m³ 小计20 m³",items)

    def test_entire_contract_volume_known_for_regular_and_blueprints(self):
        proof={"cargo_volume_m3":2,"included_volumes":{"34":1,"35":100}}
        included={"34":2,"35":1}
        report=contract_volume(proof,included,{"34":2})
        self.assertEqual(report["credited_transport_volume_m3"],2)
        self.assertEqual(report["whole_contract_volume_m3"],102)
        self.assertIn("整份合同102 m³",contract_label(report))

    def test_inconsistent_archived_volumes_show_unverified_not_invented(self):
        proof={"cargo_volume_m3":999,
               "included_volumes":{"34":10,"35":20}}
        report=contract_volume(proof,{"34":2,"35":1},{"34":2})
        self.assertIsNone(report["credited_transport_volume_m3"])
        self.assertIn("计价货物未核实",contract_label(report))
        self.assertEqual(report["whole_contract_volume_m3"],40)
        self.assertFalse(credited_volume_breakdown(report))
        self.assertIsNone(market_volume({"volume_m3":7,"cargo_volume_m3":14},3)
                          ["unit_volume_m3"])
        self.assertEqual(format_m3(None),"未核实")
        self.assertEqual(format_m3(float("nan")),"未核实")

    def test_mail_formats_preserve_numbers_and_quotas(self):
        mk={"type_id":34,"quantity":3,"source_location":1053970513596,
            "net_profit_snapshot":50_000_001,"roi_snapshot":.2,
            "source_vwap_isk_per_unit":10000000,"jita_vwap_isk_per_unit":20000000,
            **market_volume({"volume_m3":1.5,"cargo_volume_m3":4.5},3)}
        con={"contract_id":990001,"source_location":60008494,
             "contract_price":200_000_000,
             "net_profit_snapshot":51_000_000,"roi_snapshot":.15,
             **contract_volume(
                 {"cargo_volume_m3":50,"included_volumes":{"34":.5,"35":100}},
                 {"34":100,"35":1},{"34":100})}
        report={"coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                "source_input_integrity":"ALL_PARSED",
                "run_folder":"20261017T112301Z-xyz",
                "market_research_leads":[mk],
                "contract_research_leads":[con],
                "blueprint_research_leads":[]}
        subject,plain=render(report,game=False)
        _,game=render(report,game=True)
        _,rich=render_html(report)
        self.assertIn("市场1 合同1 蓝图制造0",subject)
        for body in (plain,game,rich):
            self.assertIn("单件1.5 m³",body)
            self.assertIn("合计4.5 m³",body)
            self.assertIn("计价货物50 m³",body)
            self.assertIn("整份合同150 m³",body)
            self.assertIn("Type 34×100 单件0.5 m³ 小计50 m³",body)
        self.assertIn("<url=showinfo:34>",game)
        self.assertIn('<a href=',rich)
        self.assertEqual(len(report["market_research_leads"]),1)
        self.assertEqual(len(report["contract_research_leads"]),1)

    def test_no_volume_fields_does_not_break_legacy_renderers(self):
        old={"coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
             "source_input_integrity":"ALL_PARSED",
             "run_folder":"20261017T112301Z-xyz",
             "market_research_leads":[{
                 "type_id":34,"quantity":2,"source_location":60008494,
                 "net_profit_snapshot":90_000_000,"roi_snapshot":.3,
                 "source_vwap_isk_per_unit":1_000_000,
                 "jita_vwap_isk_per_unit":2_000_000
             }],"contract_research_leads":[{
                 "contract_id":771,"source_location":60008494,
                 "contract_price":100_000_000,
                 "net_profit_snapshot":90_000_000,"roi_snapshot":.3
             }]}
        for output in (render(old)[1],render(old,game=True)[1],render_html(old)[1]):
            self.assertIn("未核实",output)
            self.assertNotIn("合计0 m³",output)


if __name__=="__main__":
    unittest.main()
