"""Contract-source monitoring: no EVE API, mail or disk writes."""
from __future__ import annotations

import unittest

from v4.contract_station_monitor import station_contract_summary


STRUCTURES = {
    "banestar": (1050474463169, "dc"),
    "cj": (1049588174021, "dc"),
    "o4t": (1040804972352, "dc"),
    "r_arkn": (1048663825563, "dc"),
    "ualx": (1046664001931, "dc"),
}


class ContractStationSummaryTests(unittest.TestCase):
    def test_five_structures_two_npc_hubs_without_jita(self):
        rows = [1049588174021]*3 + [1046664001931,60008494]*2 + [60011866] + [60003760]
        proofs = [
            {"kind":"contract","source_location":1049588174021,
             "model_candidate":True},
            {"kind":"contract","source_location":1049588174021,
             "model_candidate":False},
            {"kind":"contract","source_location":1046664001931,
             "model_candidate":True},
            {"kind":"market","source_location":60008494,
             "model_candidate":True},
            {"kind":"contract","source_location":60008494,
             "model_candidate":True},
        ]
        result = station_contract_summary(rows,proofs,structures=STRUCTURES)
        by=result["stations"]
        self.assertEqual(set(by),set(STRUCTURES)|{"amarr","dodixie"})
        self.assertNotIn("jita",by)
        self.assertEqual(by["cj"]["scoped_cash_contracts"],3)
        self.assertEqual(by["cj"]["audited_contract_proofs"],2)
        self.assertEqual(by["cj"]["shadow_model_candidates"],1)
        self.assertEqual(by["ualx"]["scoped_cash_contracts"],2)
        self.assertEqual(by["ualx"]["shadow_model_candidates"],1)
        self.assertEqual(by["amarr"]["scoped_cash_contracts"],2)
        self.assertEqual(by["amarr"]["shadow_model_candidates"],1)
        self.assertEqual(by["dodixie"]["scoped_cash_contracts"],1)
        self.assertEqual(by["r_arkn"]["scoped_cash_contracts"],0)
        self.assertEqual(by["r_arkn"]["shadow_model_candidates"],0)
        self.assertTrue(result["model_candidates_are_not_live_verified"])

    def test_legacy_scope_adds_only_selected_structures_and_npc_hubs(self):
        result = station_contract_summary(
            [1050474463169,60008494,60011866],[],
            structures={"cj":STRUCTURES["cj"],"o4t":STRUCTURES["o4t"]})
        self.assertEqual(set(result["stations"]),{"cj","o4t","amarr","dodixie"})
        self.assertEqual(result["stations"]["amarr"]["scoped_cash_contracts"],1)

    def test_duplicate_station_id_fails(self):
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            station_contract_summary([],[],structures={
                "foo":(60008494,"dc")})


if __name__ == "__main__":
    unittest.main()
