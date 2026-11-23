"""Compact reports must retain real evidence and never invent a trade result."""
import json
import unittest

from v4.celebration_crate_real_bundle_audit import compact_receipt


class CompactReceiptTests(unittest.TestCase):
    def setUp(self):
        self.detail={
            "status":"HISTORICAL_REAL_MULTI_ITEM_CONTRACT_DEPTH_AUDIT",
            "source_run":"20261123T022301Z-df2f5b1f",
            "selection_counts":{"eligible_nonblueprint_no_requests":987},
            "actual_contracts_cross_checked":350,
            "real_plex_crate_plus_other_contract_candidates":0,
            "sampled_contracts_with_two_plus_priced_item_types":321,
            "all_cross_checks_passed":True,
            "examples":[
                {"contract_id":11,"net_after_haul_isk":-200,
                 "itemized_actual_jita_order_fills":[{"order_id":42}],
                 "contains_approved_plex_crate":False,
                 "independent_cross_check_passed":True},
                {"contract_id":12,"net_after_haul_isk":-100,
                 "itemized_actual_jita_order_fills":[{"order_id":99}],
                 "contains_approved_plex_crate":False,
                 "independent_cross_check_passed":True},
                {"contract_id":13,"net_after_haul_isk":None,
                 "itemized_actual_jita_order_fills":[{"order_id":101}],
                 "independent_cross_check_passed":True},
            ],
        }

    def test_truthful_denominators_and_sorted_compact_sample(self):
        c=compact_receipt(self.detail,examples=2)
        self.assertEqual(c["actual_contracts_cross_checked"],350)
        self.assertEqual(c["real_plex_crate_plus_other_contract_candidates"],0)
        self.assertTrue(c["all_cross_checks_passed"])
        self.assertEqual([x["contract_id"] for x in c["examples_ranked_only_within_saved_sample"]],
                         [12,11])
        self.assertNotIn("itemized_actual_jita_order_fills",
                         str(c))
        self.assertTrue(c["not_trade_recommendations"])
        json.dumps(c,allow_nan=False)

    def test_missing_is_not_success_and_unknown_profit_last(self):
        self.detail["all_cross_checks_passed"]=False
        self.detail["actual_contracts_cross_checked"]=0
        c=compact_receipt(self.detail,examples=3)
        self.assertFalse(c["all_cross_checks_passed"])
        self.assertEqual([x["contract_id"] for x in c["examples_ranked_only_within_saved_sample"]],
                         [12,11,13])

    def test_invalid_sample_count_fails(self):
        with self.assertRaisesRegex(ValueError,"OUT_OF_RANGE"):
            compact_receipt(self.detail,examples=0)


if __name__=="__main__":
    unittest.main()
