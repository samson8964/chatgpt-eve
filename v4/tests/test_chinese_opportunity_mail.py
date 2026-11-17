"""Regression tests for source-backed Chinese names and all three mail lanes."""
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from v4.mail_names import compile_names, localized, load, roman
from v4.unified_review import money, render, render_html


def fixture():
    return {
        "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
        "source_input_integrity":"ALL_PARSED","run_folder":"20261117T052300Z-test",
        "mail_names":{"types":{"34":"三钛合金","17324":"等离子推进器蓝图",
                              "17325":"蓝图乙","17326":"蓝图丙","17327":"蓝图丁"},
                      "stations":{"60002065":"测试星系 IV - 卫星 4 - 测试工厂"}},
        "market_research_leads":[{"type_id":34,"quantity":2,"source_location":1049588174021,
                                  "net_profit_snapshot":84_000_000,"roi_snapshot":.27,
                                  "capital":311_000_000,"purchase_total":300_000_000,
                                  "gross_sale":412_000_000,"haul_estimate":11_000_000,
                                  "source_vwap_isk_per_unit":150_000_000,"jita_vwap_isk_per_unit":206_000_000}],
        "contract_research_leads":[{"contract_id":123456789,"source_location":60002065,
                                    "source_security_band":"HIGH","included_items":{"34":2},
                                    "credited_items":{"34":2},"contract_price":180_000_000,
                                    "investment":180_000_000,"haul_estimate_isk":0,
                                    "net_profit_snapshot":57_000_000,"roi_snapshot":.32}],
        "blueprint_research_leads":[{"contract_id":237775546,"source_location":60002065,
                                    "blueprint_type_id":17324,"production_runs_assumed":4000,
                                    "bundle_blueprint_selected":4,"bundle_blueprint_total":33,
                                    "bundle_selected_details":[
                                        {"blueprint_type_id":17324,"production_runs":4000,"contribution_isk":100_000_000},
                                        {"blueprint_type_id":17325,"production_runs":20,"contribution_isk":20_000_000},
                                        {"blueprint_type_id":17324,"production_runs":10,"contribution_isk":5_000_000},
                                        {"blueprint_type_id":17326,"production_runs":30,"contribution_isk":10_000_000}],
                                    "contract_price":31_000_000,"material_cost":932_000_000,
                                    "fee_reserve":105_000_000,"haul_estimate_isk":15_000_000,
                                    "investment":1_083_000_000,"sales_tax":42_000_000,
                                    "product_gross":1_256_000_000,"net_profit_snapshot":131_000_000,
                                    "roi_snapshot":.12,"risk_score":0}]}


class ChineseMailTests(unittest.TestCase):
    def test_units_and_missing_are_not_zero(self):
        self.assertEqual(money(2_000_000),"200万")
        self.assertEqual(money(131_000_000),"1.31亿")
        self.assertEqual(money(0),"0 ISK")
        self.assertEqual(money(None),"未核实")

    def test_all_formats_share_names_real_costs_and_run_sum(self):
        review=fixture()
        for subject,body in (render(review),render(review,game=True),render_html(review)):
            self.assertIn("市场1 合同1 蓝图制造1",subject)
            self.assertIn("三钛合金",body)
            self.assertIn("等离子推进器蓝图",body)
            self.assertIn("测试星系 IV",body)
            self.assertIn("预计净赚 1.31亿",body)
            self.assertIn("投入 10.83亿",body)
            self.assertIn("运费 1500万",body)
            self.assertIn("组合制造4,060次",body)
            self.assertIn("等离子推进器蓝图×4,010次",body)
            self.assertIn("风险分0不等于无风险",body)
            self.assertNotIn("合同 237775546",body)
            self.assertNotIn("代表蓝图17324",body)
            self.assertNotIn("空间站 60002065",body)
        self.assertIn("<url=contract:0//237775546>",render(review,game=True)[1])
        self.assertIn('href="https://eve-contract-opener.99617224.workers.dev/c/237775546"',render_html(review)[1])

    def test_missing_names_no_raw_id_and_no_invented_fee(self):
        review=fixture()
        review.pop("mail_names")
        review["blueprint_research_leads"][0].pop("haul_estimate_isk")
        for body in (render(review)[1],render(review,game=True)[1],render_html(review)[1]):
            self.assertIn("物品名称待核实",body)
            self.assertIn("运费 未核实",body)
            self.assertNotIn("物品 34",body)
            self.assertNotIn("60002065",body)

    def test_name_sanitization(self):
        review=fixture()
        review["mail_names"]["types"]["34"]='<url=contract:0//999999>危险&名称\n'
        body=render(review,game=True)[1]
        self.assertNotIn("<url=contract:0//999999>",body)
        self.assertNotIn("<url=contract:0//999999>",render_html(review)[1])

    def test_30_leads_with_long_names_fit_native_mail(self):
        review=fixture()
        review["mail_names"]["types"]={k:"超长中文物品名称"*14 for k in review["mail_names"]["types"]}
        review["mail_names"]["stations"]["60002065"]="超长空间站名字"*14
        m,c,b=[review[k][0] for k in ("market_research_leads","contract_research_leads","blueprint_research_leads")]
        review["market_research_leads"]=[dict(m,type_id=34) for i in range(10)]
        review["contract_research_leads"]=[dict(c,contract_id=123456789+i,
                                              included_items={"34":2,"17325":4,"17326":3},
                                              contract_history_reference_share=.1) for i in range(10)]
        review["blueprint_research_leads"]=[dict(b,contract_id=237775546+i) for i in range(10)]
        subject,body=render(review,game=True)
        self.assertIn("市场10 合同10 蓝图制造10",subject)
        self.assertLessEqual(len(body),9000)
        self.assertEqual(body.count("<url="),30)
        self.assertEqual(body.count("</url>"),30)

    def test_official_sde_localization_and_station_orbit(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"test.zip"
            data={
                "types.jsonl":[{"_key":34,"name":{"zh":"三钛合金","en":"Tritanium"}},
                               {"_key":35,"name":{"en":"Pyerite"}}],
                "mapSolarSystems.jsonl":[{"_key":1,"name":{"zh":"吉他","en":"Jita"}}],
                "npcCorporations.jsonl":[{"_key":2,"name":{"zh":"海军","en":"Navy"}}],
                "stationOperations.jsonl":[{"_key":3,"operationName":{"zh":"组装车间"}}],
                "mapPlanets.jsonl":[{"_key":4,"solarSystemID":1,"celestialIndex":4}],
                "mapMoons.jsonl":[{"_key":5,"orbitID":4,"orbitIndex":4,"celestialIndex":7}],
                "npcStations.jsonl":[{"_key":60003760,"orbitID":5,"ownerID":2,
                                      "operationID":3,"useOperationName":True}]}
            with zipfile.ZipFile(path,"w") as z:
                for name,rows in data.items():
                    z.writestr(name,"\n".join(json.dumps(r,ensure_ascii=False) for r in rows))
            cache=compile_names(path,min_types=2,min_stations=1)
            self.assertEqual(cache["types"]["34"],"三钛合金")
            self.assertEqual(cache["types"]["35"],"Pyerite")
            self.assertEqual(cache["stations"]["60003760"],"吉他 IV - 卫星 4 - 海军 组装车间")
            self.assertEqual(load(Path(d)),{})


if __name__=="__main__":
    unittest.main()
