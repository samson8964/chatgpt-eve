"""V4 global optimistic versus Jita-depth scope and mail-stage audit regression."""
import json
import tempfile
import unittest
from pathlib import Path

try:
    import pandas as pd
    from v4.market_gap_audit import global_candidates, global_to_jita_attribution, deep_to_mail
except ImportError:
    pd = None


@unittest.skipUnless(pd is not None, "requires pandas (full V4 runtime)")
class GapAttributionTests(unittest.TestCase):
    def test_one_global_population_multiple_jita_outcomes(self):
        data=[]
        idx=1000
        def add(loc,typ,buy,price,qty):
            nonlocal idx
            idx+=1
            data.append(dict(
                order_id=idx,location_id=loc,type_id=typ,is_buy_order=buy,
                price=price,volume_remain=qty))
        JITA=60003760; AMARR=60008494; DODIXIE=60011866
        REMOTE=60009000; OTHER=60009001
        # Approved public and Jita depth >= 50m.
        add(AMARR,34,False,1_000_000,100)
        add(JITA,34,True,2_000_000,100)
        # Unapproved public source; Jita could liquidate 100m GROSS.
        add(REMOTE,35,False,1_000_000,100)
        add(JITA,35,True,2_000_000,100)
        # Global best BID is elsewhere, not Jita: Jita gross only 20m.
        add(REMOTE,36,False,1_000_000,100)
        add(OTHER,36,True,2_000_000,100)
        add(JITA,36,True,1_200_000,100)
        # No Jita bids even though best bid elsewhere.
        add(REMOTE,37,False,1_000_000,100)
        add(OTHER,37,True,2_000_000,100)
        # Jita as source is not a Jita-import opportunity.
        add(JITA,38,False,1_000_000,100)
        add(OTHER,38,True,2_000_000,100)
        # Very shallow Jita depth: 10 units cover only 10m gross.
        add(DODIXIE,39,False,1_000_000,100)
        add(OTHER,39,True,2_000_000,100)
        add(JITA,39,True,2_000_000,10)
        # Jita bid is <= source ask.
        add(DODIXIE,40,False,1_000_000,100)
        add(OTHER,40,True,2_000_000,100)
        add(JITA,40,True,900_000,100)
        raw=pd.DataFrame(data)
        found=global_candidates(raw)
        self.assertEqual(len(found),7)
        result=global_to_jita_attribution(raw,found,{
            "stations":{str(REMOTE):{"band":"HIGH"}}
        })
        self.assertEqual(result["global_optimistic_public_pairs"],7)
        self.assertEqual(result["jita_depth_gross_at_least_50m_any_public_source"],2)
        self.assertEqual(result["jita_depth_gross_at_least_50m_public_approved_sources"],1)
        self.assertEqual(result["jita_depth_gross_at_least_50m_public_unapproved_sources"],1)
        self.assertEqual(result["unapproved_gross_candidates_by_npc_security"]["HIGH"],1)
        reasons=result["global_candidate_explained_by_jita_exit"]
        for reason in (
            "JITA_AS_SOURCE_NOT_A_CROSS_STATION_TRADE",
            "NO_JITA_BUY",
            "JITA_BEST_BID_NOT_ABOVE_SOURCE_ASK",
        ):
            self.assertEqual(reasons[reason],1)
        # One expensive local quote and one shallow Jita book both produce
        # less than the 50m matched-depth gross gate.
        self.assertEqual(reasons["JITA_MATCHED_GROSS_BELOW_50M"],2)
        self.assertEqual(sum(reasons.values()),7)

    def test_deep_proof_attribution_and_email_gate(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)
            good={
                "kind":"market","status":"WATCH","model_candidate":True,
                "reason":"LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED",
                "source_location":60008494,
                "destination_location":60003760,
                "valuation_location_id":60003760,
                "valuation_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE",
                "type_id":34,"quantity":10,"quantity_optimized":True,
                "profit":90_000_000,"roi":.20,"density":5_000,
                "stress_profit":60_000_000,"cost":450_000_000,
                "source_vwap_isk_per_unit":10_000_000,
                "jita_vwap_isk_per_unit":20_000_000,
                "executed_sell_cost":100_000_000,
                "executed_jita_buy_gross":200_000_000,
            }
            near={
                **good, "model_candidate":False,
                "reason":"BELOW_GATE_OR_STRESS",
                "profit":90_000_000,"stress_profit":20_000_000,
                "type_id":35
            }
            no_route={
                "kind":"market","source_location":60011866,
                "type_id":36,"reason":"HAUL_UNVERIFIED",
                "model_candidate":False
            }
            path=folder/"all_proofs.jsonl"
            path.write_text("".join(json.dumps(x)+"\n" for x in [good,near,no_route]))
            result=deep_to_mail(folder,{"market_proofs_examined":3})
            self.assertTrue(result["deep_proof_count_matches"])
            self.assertEqual(result["model_candidates"],1)
            self.assertEqual(result["eligible_market_research_leads_before_display_cap"],1)
            self.assertEqual(result["maximum_market_leads_shown_in_email"],1)
            self.assertEqual(result["market_proof_reasons"]["BELOW_GATE_OR_STRESS"],1)
            self.assertEqual(result["failed_economic_gates_multi_label_overlaps"]
                             ["JITA_BUY_STRESS_NET_NOT_ABOVE_50M"],1)


if __name__=="__main__":
    unittest.main()
