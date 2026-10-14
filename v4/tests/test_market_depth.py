"""Station coverage completeness and top-five DISTINCT price-level arithmetic."""
import json
import tempfile
import unittest
from pathlib import Path

from v4.engine import Order
from v4.market_depth import STATIONS, top_price_levels, station_sell_census
from v4.market_station_audit import summarize


def order(*, lid, typ, price, buy=False, remaining=50, ident=1):
    return Order(order_id=ident, type_id=typ, location_id=lid,
                 buy=buy, price=price, remaining=remaining)


class MarketDepthTests(unittest.TestCase):
    def test_same_price_orders_count_as_one_level(self):
        asks=[order(lid=STATIONS["4-H"],typ=34,price=p,ident=i)
              for i,p in enumerate((2e6,1e6,1e6,3e6,4e6,5e6,6e6),1)]
        bids=[order(lid=60003760,typ=34,price=p,buy=True,ident=i)
              for i,p in enumerate((8e6,8e6,10e6,9e6,7e6,6e6),20)]
        sell=top_price_levels(asks,buy=False)
        buy=top_price_levels(bids,buy=True)
        self.assertEqual(sell["group_count"],5)
        self.assertEqual(sell["group_prices_isk"],
                         [1e6,2e6,3e6,4e6,5e6])
        self.assertEqual(sell["simple_mean_isk_per_unit"],3e6)
        self.assertEqual(buy["group_count"],5)
        self.assertEqual(buy["group_prices_isk"],
                         [10e6,9e6,8e6,7e6,6e6])
        self.assertEqual(buy["simple_mean_isk_per_unit"],8e6)

    def test_sparse_levels_never_fabricates_missing_fifth(self):
        asks=[order(lid=STATIONS["O4T"],typ=34,price=3e6)]
        actual=top_price_levels(asks,buy=False)
        self.assertEqual(actual["group_count"],1)
        self.assertEqual(actual["simple_mean_isk_per_unit"],3e6)
        self.assertEqual(top_price_levels([],buy=True)["group_count"],0)

    def test_all_station_sells_counted_even_when_no_jita_bid(self):
        h=STATIONS["4-H"]
        o=STATIONS["O4T"]
        books={
            (h,34,False):[order(lid=h,typ=34,price=2e6,remaining=100)],
            (h,35,False):[order(lid=h,typ=35,price=12e6)],
            (o,36,False):[order(lid=o,typ=36,price=1e6)],
            (o,37,False):[order(lid=o,typ=37,price=3e6)],
            (o,37,True):[order(lid=o,typ=37,price=1e6,buy=True)],
            (60003760,34,True):[order(lid=60003760,typ=34,price=10e6,buy=True)],
            (60003760,35,True):[order(lid=60003760,typ=35,price=11e6,buy=True)],
            (60003760,37,True):[order(lid=60003760,typ=37,price=4e6,buy=True)],
        }
        result=station_sell_census(books)
        self.assertEqual(result["4-H"]["active_sell_type_ids"],2)
        self.assertEqual(result["4-H"]["sell_types_with_jita_buy"],2)
        self.assertEqual(result["4-H"]["sell_types_best_price_crossed"],1)
        self.assertEqual(result["4-H"]["sell_types_optimistic_gate_passed"],1)
        self.assertEqual(result["O4T"]["active_sell_type_ids"],2)
        self.assertEqual(result["O4T"]["sell_types_with_jita_buy"],1)
        self.assertEqual(result["O4T"]["sell_types_without_jita_buy"],1)
        self.assertEqual(result["O4T"]["sell_types_best_price_crossed"],1)
        self.assertEqual(result["O4T"]["sell_types_optimistic_gate_passed"],0)

    def test_old_scan_cannot_invent_distinct_item_counts(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)/"runs"/"20261014T122301Z-old"
            folder.mkdir(parents=True)
            (folder/"manifest.json").write_text(
                '{"status":"SHADOW_RECORDED"}',encoding="utf-8")
            (folder/"deep_shadow.json").write_text(json.dumps({
                "structure_health":{
                    "four_h":{"status":"COMPLETE","orders":392},
                    "cj":{"status":"COMPLETE","orders":400},
                    "o4t":{"status":"COMPLETE","orders":91}}}),encoding="utf-8")
            (folder/"all_proofs.jsonl").write_text(json.dumps({
                "kind":"market","source_location":STATIONS["4-H"],
                "model_candidate":True})+"\n",encoding="utf-8")
            output=summarize(Path(td))
            self.assertIsNone(output["stations"]["4-H"]["active_sell_type_ids"])
            self.assertEqual(output["stations"]["4-H"]["total_structure_orders"],392)
            self.assertEqual(output["stations"]["4-H"]["full_depth_market_pairs_evaluated"],1)
            self.assertEqual(output["stations"]["O4T"]["total_structure_orders"],91)
            self.assertEqual(output["stations"]["O4T"]["full_depth_market_pairs_evaluated"],0)
            self.assertEqual(output["limitations"],
                             "OLDER_SCAN_HAS_NO_PERSISTED_DISTINCT_SELL_TYPE_CENSUS")

    def test_new_scan_has_precise_distinct_sell_type_counts(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)/"runs"/"20261014T130000Z-new"
            folder.mkdir(parents=True)
            (folder/"manifest.json").write_text(
                '{"status":"SHADOW_RECORDED"}',encoding="utf-8")
            (folder/"deep_shadow.json").write_text(json.dumps({
                "market_station_sell_census":{
                    "4-H":{"active_sell_type_ids":234,"active_sell_orders":456,
                           "sell_types_with_jita_buy":201,
                           "sell_types_without_jita_buy":33,
                           "sell_types_best_price_crossed":19,
                           "sell_types_optimistic_gate_passed":2},
                    "O4T":{"active_sell_type_ids":100,"active_sell_orders":190,
                           "sell_types_with_jita_buy":67,
                           "sell_types_without_jita_buy":33,
                           "sell_types_best_price_crossed":8,
                           "sell_types_optimistic_gate_passed":0},
                }}),encoding="utf-8")
            (folder/"all_proofs.jsonl").write_text("",encoding="utf-8")
            result=summarize(Path(td))
            self.assertEqual(result["stations"]["4-H"]["active_sell_type_ids"],234)
            self.assertEqual(result["stations"]["4-H"]["sell_types_with_jita_buy"],201)
            self.assertTrue(result["stations"]["4-H"]["historical_type_count_complete"])
            self.assertIsNone(result["limitations"])


if __name__=="__main__":
    unittest.main()
