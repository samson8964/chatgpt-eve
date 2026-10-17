import json
import math
import tempfile
import unittest
from pathlib import Path

from v4.engine import Order, Policy, order_index, market_proof, contract_proof, quarantine_snapshot_candidate, parse_orders_strict, parse_orders_with_quarantine
from v4.state import Ledger


def o(i, price, buy, qty=100, tid=10, where=1):
    return Order(i, tid, where, buy, price, qty)


class V4EngineTests(unittest.TestCase):
    def test_invalid_public_order_fails_scan_not_silent_skip(self):
        rows=[{'order_id':11,'type_id':10,'location_id':1,
               'is_buy_order':False,'price':100,'volume_remain':2},
              {'order_id':12,'type_id':10,'location_id':1,
               'is_buy_order':False,'price':float('nan'),'volume_remain':2}]
        with self.assertRaisesRegex(ValueError,'INCOMPLETE_PUBLIC_ORDER_BOOK:1'):
            parse_orders_strict(rows,source='PUBLIC')

    def test_quarantine_preserves_valid_book_and_every_invalid_raw_row(self):
        rows=[{'order_id':1,'type_id':10,'location_id':1,'is_buy_order':False,
               'price':100,'volume_remain':3},
              {'order_id':2,'type_id':10,'location_id':1,'is_buy_order':False,
               'price':100,'volume_remain':0},
              {'order_id':3,'type_id':10,'location_id':1,'is_buy_order':False,
               'price':'nan','volume_remain':5}]
        good,bad=parse_orders_with_quarantine(rows,source='PUBLIC')
        self.assertEqual(len(good),1)
        self.assertEqual(len(bad),2)
        self.assertEqual(len({r['instance'] for r in bad}),2)
        self.assertEqual([r['status'] for r in bad],['RESEARCH','RESEARCH'])
        self.assertEqual([r['reason'] for r in bad],
                         ['SOURCE_ORDER_ZERO_REMAINING','SOURCE_ORDER_INVALID'])
        self.assertEqual([r['row_index'] for r in bad],[1,2])
        json.dumps(bad,allow_nan=False)

    def test_zero_remaining_keeps_proof_but_does_not_create_tradable_order(self):
        base={'order_id':7444436938,'type_id':482,'location_id':60003760,
              'is_buy_order':'false','price':518100.0,
              'min_volume':1,'range':'region'}
        data=[dict(base,volume_remain=0)]
        valid,records=parse_orders_with_quarantine(data,source='PUBLIC')
        self.assertEqual(valid,[])
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['reason'],'SOURCE_ORDER_ZERO_REMAINING')
        self.assertEqual(records[0]['kind'],'input_non_actionable')
        self.assertEqual(records[0]['status'],'RESEARCH')
        self.assertEqual(records[0]['order_id_hint'],'7444436938')

    def test_malformed_orders_with_zero_volume_remain_invalid(self):
        base={'order_id':44,'type_id':10,'location_id':60003760,
              'is_buy_order':False,'price':5000.0,
              'volume_remain':0,'min_volume':1}
        cases=[
            dict(base,price=-5),
            dict(base,price='nan'),
            dict(base,order_id=-1),
            dict(base,type_id=0),
            dict(base,volume_remain=-1),
            dict(base,volume_remain=0.5),
            dict(base,volume_remain='missing'),
        ]
        valid,records=parse_orders_with_quarantine(cases,source='PUBLIC')
        self.assertEqual(valid,[])
        self.assertEqual(len(records),len(cases))
        self.assertTrue(all(r['reason']=='SOURCE_ORDER_INVALID' for r in records))
        json.dumps(records,allow_nan=False)

    def test_valid_order_source_is_fully_preserved(self):
        rows=[{'order_id':i,'type_id':10,'location_id':1,
               'is_buy_order':'true','price':100,'volume_remain':2}
              for i in range(1,52)]
        got=parse_orders_strict(rows,source='PUBLIC')
        self.assertEqual(len(got),len(rows))
        self.assertEqual(len({o.order_id for o in got}),len(rows))

    def test_every_order_indexed_no_old_seen_block(self):
        idx = order_index([o(i, i+1, False) for i in range(1, 1001)])
        self.assertEqual(len(idx[(1, 10, False)]), 1000)

    def test_order_instance_changes_with_new_real_order(self):
        policy = Policy(profit_floor=10, min_roi=0.05, min_density=1)
        kw = dict(source_location=1, destination_location=2, type_id=10,
                  volume_m3=1, haul_isk=10, policy=policy, allowed=True, fresh=True)
        a = market_proof([o(1, 10, False), o(3, 11, False)], [o(10, 30, True, where=2), o(11, 29, True, where=2)], **kw)
        b = market_proof([o(2, 10, False), o(3, 11, False)], [o(10, 30, True, where=2), o(11, 29, True, where=2)], **kw)
        self.assertEqual(a['status'], 'MAIL')
        self.assertNotEqual(a['instance'], b['instance'])

    def test_missing_volume_fails_closed(self):
        x = market_proof([o(1,10,False)], [o(2,20,True,where=2)],
            source_location=1, destination_location=2, type_id=10, volume_m3=None,
            haul_isk=1, allowed=True, fresh=True)
        self.assertNotEqual(x['status'], 'MAIL')

    def test_unverified_route_fails_closed(self):
        x = market_proof([o(1,10,False)], [o(2,20,True,where=2)],
            source_location=1, destination_location=2, type_id=10, volume_m3=1,
            haul_isk=1, allowed=False, fresh=True)
        self.assertEqual(x['reason'], 'SOURCE_OR_ROUTE_UNVERIFIED')

    def test_contract_missing_depth(self):
        c = contract_proof({'contract_id':123,'price':100,'type':'item_exchange'},
            {10:100}, {10:[o(1,2,True,qty=5)]}, {10:1},
            haul_isk=1, allowed=True, fresh=True,
            item_classifications={10:'regular'})
        self.assertEqual(c['status'], 'WATCH')

    def test_blueprint_copy_cannot_be_liquidated_as_bpo(self):
        # Same type_id as expensive BPO order, but contract item is a copy.
        # Neither unknown nor identified blueprint is eligible for cash mail.
        c = {'contract_id':236186629,'price':1_600_000,'type':'item_exchange'}
        market_bids = {17477:[o(42,1_000_000_000,True,qty=1,tid=17477),
                              o(43,950_000_000,True,qty=1,tid=17477)]}
        for classification in (None, {17477:'blueprint_copy'}, {17477:'blueprint_original'}):
            proof = contract_proof(c,{17477:1},market_bids,{17477:1},
                haul_isk=0,allowed=True,fresh=True,item_classifications=classification)
            self.assertEqual(proof['status'],'RESEARCH',proof)
            self.assertEqual(proof['reason'],'ITEM_CLASSIFICATION_UNVERIFIED_OR_BLUEPRINT')
            json.dumps(proof,allow_nan=False)

    def test_insufficient_stress_depth_is_null_not_infinity(self):
        c={'contract_id':1234,'price':100,'type':'item_exchange'}
        bids={10:[o(1,10000,True,qty=2),o(2,9000,True,qty=1)]}
        proof=contract_proof(c,{10:2},bids,{10:1},haul_isk=1,
            allowed=True,fresh=True,item_classifications={10:'regular'},
            policy=Policy(profit_floor=1,min_roi=.01,min_density=1))
        self.assertEqual(proof['status'],'WATCH')
        self.assertIsNone(proof['stress_profit'])
        json.dumps(proof,allow_nan=False)

    def test_json_rejects_nonfinite_economic_values(self):
        c={'contract_id':1235,'price':100,'type':'item_exchange'}
        bids={10:[o(1,10000,True,qty=2),o(2,9000,True,qty=2)]}
        proof=contract_proof(c,{10:2},bids,{10:1},haul_isk=1,
            allowed=True,fresh=True,item_classifications={10:'regular'},
            policy=Policy(profit_floor=1,min_roi=.01,min_density=1))
        self.assertTrue(all(not isinstance(v,float) or math.isfinite(v)
            for v in proof.values()))
        json.dumps(proof,allow_nan=False)

    def test_shadow_quarantines_market_and_contract_candidates(self):
        for kind in ("market","contract"):
            proof={"status":"MAIL","instance":"contract:999" if kind=="contract" else "market:999","kind":kind}
            quarantine_snapshot_candidate(proof)
            self.assertEqual(proof["status"],"WATCH")
            self.assertTrue(proof["model_candidate"])
            self.assertEqual(proof["reason"],"LIVE_ORDER_AND_CONTRACT_NOT_REVALIDATED")
            json.dumps(proof,allow_nan=False)

    def test_seen_never_blocks_new_beyond_top_ten(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Ledger(str(Path(d)/'ledger.db'))
            # All 100 opportunities evaluated; 10 previously sent; after ranking
            # other 90 must still be eligible for outbox.
            proofs = [{'instance':f'i{i}', 'family':'f', 'status':'MAIL'} for i in range(100)]
            ledger.record_run('r1',{},'COMPLETE')
            ledger.record_proofs('r1',proofs)
            self.assertEqual(ledger.enqueue('r1',proofs[:10],['MikeChong']),10)
            for i in range(10):
                ledger.mark_sent(f'i{i}','MikeChong')
            ledger.record_run('r2',{},'COMPLETE')
            ledger.record_proofs('r2',proofs)
            self.assertEqual(ledger.enqueue('r2',proofs,['MikeChong']),90)
            self.assertEqual(len(ledger.pending('MikeChong')),90)
            ledger.close()


if __name__ == '__main__':
    unittest.main()
