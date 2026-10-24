"""CCP NPC station catalog and contract ROI mail gate (network-free tests)."""
from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from v4.npc_station_catalog import (
    compile_sde_zip, install, load_catalog, security_band, INDEX
)
# The lightweight Reliability CI omits pandas/requests; only the isolated
# full-dependency suite can import v4.deep_scan for route-cost tests.
try:
    from v4.deep_scan import haul, JITA
except ImportError:
    haul, JITA = None, 60003760
from v4.contract_review import make_review


class NPCSecurityCatalogTests(unittest.TestCase):
    def test_ccp_rounding_and_nullsec_are_not_misclassified(self):
        for raw in (.45, .5, 1, .999):
            self.assertEqual(security_band(raw), "HIGH")
        for raw in (.449999, .4, .049, .0001):
            self.assertEqual(security_band(raw), "LOW")
        for raw in (0, -0.0001, -.1, -1, float("nan"), None):
            self.assertIsNone(security_band(raw))

    def test_official_sde_jsonl_install_and_cached_index(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / "mini.zip"
            # Large enough to exercise the production fail-closed completeness
            # checks, but no external URL, downloader or ESI credentials needed.
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("sde/mapSolarSystems.jsonl", "".join(
                    json.dumps({"_key":30000001+i,
                                "securityStatus":(.6 if i%3==0
                                                  else .4 if i%3==1 else -.1),
                                "regionID":10000001})+"\n"
                    for i in range(3000)))
                z.writestr("sde/npcStations.jsonl", "".join(
                    json.dumps({"_key":60000004+i,
                                "solarSystemID":30000001+(i%3000)})+"\n"
                    for i in range(1800)))
            summary=install(root,sde_zip=archive)
            cat=load_catalog(root)
            self.assertIsNotNone(cat)
            self.assertEqual(summary["npc_station_total"],1800)
            self.assertEqual(summary["highsec_stations"],600)
            self.assertEqual(summary["lowsec_stations"],600)
            self.assertEqual(summary["nullsec_excluded"],600)
            self.assertEqual(len(cat["stations"]),1200)
            self.assertEqual(cat["stations"]["60000004"]["band"],"HIGH")
            self.assertEqual(cat["stations"]["60000005"]["band"],"LOW")
            self.assertNotIn("60000006",cat["stations"])
            self.assertTrue((root/INDEX).is_file())
            self.assertTrue(archive.is_file())  # user's pre-downloaded ZIP is preserved

    @unittest.skipIf(haul is None, "full market dependencies not available")
    def test_remote_npc_haul_has_security_cost_not_free_shipping(self):
        stations={JITA:{"system":30000142,"region":10000002}}
        sources={
            60001421: {"band":"HIGH","security":.9},
            60001422: {"band":"LOW","security":.2}}
        self.assertIsNone(haul(60001421,JITA,500,stations))
        self.assertEqual(haul(60001421,JITA,500,stations,sources),15375000)
        self.assertEqual(haul(60001422,JITA,500,stations,sources),51250000)
        self.assertEqual(haul(JITA,JITA,500,stations,sources),0)
        self.assertIsNone(haul(60001423,JITA,500,stations,sources))


class ContractROIResearchTests(unittest.TestCase):
    def test_every_sub_ten_percent_contract_is_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            name="20261015T082300Z-fixture"
            folder=root/"runs"/name
            folder.mkdir(parents=True)
            (folder/"manifest.json").write_text(json.dumps({
                "status":"SHADOW_RECORDED",
                "mail_enabled":False,"ready_for_production":False,
                "coverage_gate":"INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED",
                "source_input_integrity":"ALL_PARSED"}),encoding="utf-8")
            (folder/"deep_shadow.json").write_text(json.dumps({
                "status":"SHADOW_ONLY_NO_LIVE_ALERTS",
                "contract_pricing_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
                "contract_approved_locations_examined":4
            }),encoding="utf-8")
            rows=[]
            for i,roi in enumerate((.02,.099999,.10,.11)):
                rows.append({
                    "kind":"contract",
                    "contract_id":236900001+i,
                    "source_location":60000100+i,
                    "source_security_band":"HIGH" if i%2==0 else "LOW",
                    "destination_location":JITA,
                    "valuation_location_id":JITA,
                    "valuation_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE",
                    "reason":"BELOW_GATE_OR_STRESS",
                    "status":"WATCH",
                    "net_profit":60_000_000,
                    "roi":roi,
                    "cost":100_000_000,
                    "stress_profit":51_000_000,
                    "contract_price":15_000_000,
                    "haul_cost_estimate_isk":20_000_000,
                    "included_items":{"34":10}
                })
            (folder/"all_proofs.jsonl").write_text(
                "".join(json.dumps(row)+"\n" for row in rows),encoding="utf-8")
            report=make_review(root,limit=None)
            self.assertEqual(report["contract_proofs_audited"],4)
            self.assertEqual(report["research_leads_total"],2)
            self.assertEqual(set(x["contract_id"] for x in report["research_leads"]),
                             {236900003,236900004})
            self.assertEqual(set(x["source_security_band"]
                                 for x in report["research_leads"]),{"HIGH","LOW"})


if __name__=="__main__":
    unittest.main()
