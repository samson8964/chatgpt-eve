import tempfile
import unittest
from pathlib import Path

from v4.engine import Order, Policy, order_index, market_proof, contract_proof
from v4.state import Ledger


def o(i, price, buy, qty=100, tid=10, where=1):
    return Order(i, tid, where, buy, price, qty)


class V4EngineTests(unittest.TestCase):
    def test_every_order_indexed_no_old_seen_block(self):
        idx = order_index([o(i, i+1, False) for i in range(1, 1001)])
        self.assertEqual(len(idx[(1, 10, False)]), 1000)

    def test_order_instance_changes_with_new_real_order(self):
        policy = Policy(profit_floor=10, min_roi=0.05, min_density=1)
        kw = dict(source_location=1, destination_location=2, type_id=10,
                  volume_m3=1, haul_isk=10, policy=policy, allowed=True, fresh=True)
        a = market_proof([o(1, 10, False)], [o(10, 30, True, where=2), o(11, 29, True, where=2)], **kw)
        b = market_proof([o(2, 10, False)], [o(10, 30, True, where=2), o(11, 29, True, where=2)], **kw)
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
            haul_isk=1, allowed=True, fresh=True)
        self.assertEqual(c['status'], 'WATCH')

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
