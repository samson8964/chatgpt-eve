"""Synthetic tests; never reads or mutates production data."""
import unittest
from v4.contract_opportunity_loss_audit import (
    combine, analyze_rows, BP_BASIS, FEE_BASIS, CONTRACT_VALUATION_BASIS
)
class Exclusion:
    def blocks_contract(self, items): return "999" in items
    def blocks_blueprint(self, b, p): return b==999

def pair():
    o=dict(kind="contract",contract_id=1,contract_price=100_000_000,
           source_location=60003760,valuation_location_id=60003760,
           destination_location=60003760,valuation_basis=CONTRACT_VALUATION_BASIS,
           status="WATCH",reason="BELOW_GATE_OR_STRESS",net_profit=-20_000_000,
           roi=-.2,cost=100_000_000,energy_crystal_value_share=0,
           included_items={"11":1,"22":1},credited_items={"11":1},
           contract_blueprint_evidence={"BPC":1})
    b=dict(kind="blueprint_manufacturing",contract_id=1,contract_price_isk=100_000_000,
           source_location=60003760,blueprint_kind="BPC",valuation_basis=BP_BASIS,
           status="WATCH",net_profit=-10_000_000,roi=-.05,cost=200_000_000,
           facility_fee_status=FEE_BASIS,manufacturing_fee_snapshot_verified=True,
           jita_material_top5_prices_observed=True,jita_product_top5_prices_observed=True,
           risk_score=0,bundle_selected_details=[{"blueprint_type_id":22,"product_type_id":33}],
           model_candidate=False)
    return o,b
class AuditTests(unittest.TestCase):
    def test_full_price_once_rescues_mixed(self):
        o,b=pair();r=combine(o,b)
        self.assertEqual(r["net_profit"],70_000_000)
        self.assertEqual(r["cost"],200_000_000)
        self.assertAlmostEqual(r["roi"],.35)
        a=analyze_rows([o,b],Exclusion())
        self.assertEqual(a["mixed_additional_candidates"],1)
        self.assertEqual(a["ordinary_current_candidates_before_top10"],0)
        self.assertEqual(a["manufacturing_current_candidates_before_top10"],0)
    def test_overlapping_assets_rejected(self):
        o,b=pair();o["credited_items"]={"22":1}
        self.assertIsNone(combine(o,b))
    def test_wrong_price_rejected(self):
        o,b=pair();b["contract_price_isk"]+=1
        self.assertIsNone(combine(o,b))
    def test_missing_bpc_proof_counted(self):
        o,b=pair();a=analyze_rows([o],Exclusion())
        self.assertEqual(a["bpc_contracts_without_manufacturing_proof"],1)
    def test_missing_fee_not_combined(self):
        o,b=pair();b["manufacturing_fee_snapshot_verified"]=False
        a=analyze_rows([o,b],Exclusion())
        self.assertEqual(a["mixed_additional_candidates"],0)
        self.assertEqual(a["manufacturing_missing_verified_fee"],1)
    def test_ship_exclusion_retained(self):
        o,b=pair();o["included_items"]["999"]=1
        self.assertEqual(analyze_rows([o,b],Exclusion())["mixed_additional_candidates"],0)
    def test_duplicate_proof_rejected(self):
        o,b=pair()
        with self.assertRaisesRegex(ValueError,"DUPLICATE_CONTRACT_PROOF"):
            analyze_rows([o,o,b],Exclusion())
if __name__=="__main__":
    unittest.main()
