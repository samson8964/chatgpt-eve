"""Regression tests for EVE V4 full private structure pagination over unstable links."""
import unittest

from v4.structure_transport import all_structure_orders


STRUCTURES = {
    "four_h": (111, "main"),
    "cj": (222, "cj"),
    "o4t": (333, "dc"),
}


class StructureTransportTests(unittest.TestCase):
    def read(self, fetch, attempts=3):
        waits=[]
        result=all_structure_orders(
            "unit-test-key", structures=STRUCTURES, worker="https://worker.invalid",
            fetch=fetch, sleep=waits.append, jitter=lambda: 0.0,
            page_attempts=attempts, pace_seconds=0)
        return result, waits

    def test_all_lanes_all_pages_no_missing_orders(self):
        expected={111:3,222:2,333:4}
        def fetch(url, params, headers, timeout):
            lid,page=params["structure_id"],params["page"]
            self.assertEqual(timeout,(10,55))
            self.assertEqual(headers["Authorization"],"Bearer unit-test-key")
            return ({"ok":True,"structure_id":lid,"page":page,
                     "pages":expected[lid],"orders":[{"order_id":lid*100+page}]}, {})
        (orders,health),waits=self.read(fetch)
        self.assertEqual(len(orders),9)
        self.assertEqual(waits,[])
        self.assertTrue(all(h["status"]=="COMPLETE" for h in health.values()))
        self.assertEqual(health["four_h"]["pages_fetched"],3)
        self.assertEqual(health["cj"]["orders"],2)

    def test_windows_10054_transient_single_page_recovered(self):
        calls={}
        def fetch(url,params,headers,timeout):
            lid,page=params["structure_id"],params["page"]
            calls[lid,page]=calls.get((lid,page),0)+1
            if (lid,page)==(222,2) and calls[lid,page]<3:
                raise ConnectionResetError(10054,"Connection reset")
            return ({"ok":True,"structure_id":lid,"page":page,"pages":2,
                     "orders":[{"order_id":lid*10+page}]},{})
        (orders,health),waits=self.read(fetch)
        self.assertEqual(len(orders),6)
        self.assertEqual(health["cj"]["status"],"COMPLETE")
        self.assertEqual(health["cj"]["transient_retries"],2)
        self.assertEqual(len(waits),2)

    def test_retry_exhaustion_discards_partial_lane_only(self):
        def fetch(url,params,headers,timeout):
            lid,page=params["structure_id"],params["page"]
            if lid==222 and page==2:
                raise ConnectionResetError(10054,"Connection reset")
            return ({"ok":True,"structure_id":lid,"page":page,"pages":2,
                     "orders":[{"order_id":lid*10+page}]},{})
        (orders,health),waits=self.read(fetch,attempts=3)
        self.assertEqual(len(orders),4)
        self.assertTrue(all(row["order_id"]//10 != 222 for row in orders))
        self.assertEqual(health["cj"]["status"],"FAILED")
        self.assertEqual(health["cj"]["reason"],"TRANSIENT_EXHAUSTED")
        self.assertEqual(health["cj"]["failed_page"],2)
        self.assertEqual(health["cj"]["pages_fetched"],1)
        self.assertEqual(len(waits),2)
        self.assertNotIn("unit-test-key",str(health))

    def test_access_denied_403_does_not_retry(self):
        calls=0
        class HTTPFailure(OSError):
            def __init__(self):
                self.response=type("Response",(),{"status_code":403})()
        def fetch(url,params,headers,timeout):
            nonlocal calls
            calls+=1
            raise HTTPFailure()
        (_,health), waits = self.read(fetch)
        self.assertEqual(calls,3)
        self.assertEqual(waits,[])
        self.assertTrue(all(v["reason"]=="NONRETRYABLE_REQUEST" for v in health.values()))
        self.assertTrue(all(v["http_status"] == 403 for v in health.values()))
        self.assertNotIn("Bearer ", str(health))

    def test_429_retry_succeeds(self):
        calls={}
        class HTTPFailure(OSError):
            def __init__(self):
                self.response=type("Response",(),{"status_code":429})()
        def fetch(url,params,headers,timeout):
            lid,page=params["structure_id"],params["page"]
            calls[lid]=calls.get(lid,0)+1
            if calls[lid]==1:raise HTTPFailure()
            return {"ok":True,"structure_id":lid,"page":page,"pages":1,
                    "orders":[]},{}
        (_,health), waits=self.read(fetch)
        self.assertEqual(len(waits),3)
        self.assertTrue(all(v["transient_retries"]==1 for v in health.values()))
        self.assertTrue(all(v["status"] == "COMPLETE" for v in health.values()))

    def test_page_count_drift_fails_closed(self):
        def fetch(url,params,headers,timeout):
            page=params["page"];lid=params["structure_id"]
            return {"ok":True,"structure_id":lid,"page":page,
                    "pages":3 if page==2 else 2,
                    "orders":[{"order_id":lid*10+page}]},{}
        (orders,health), waits=self.read(fetch)
        self.assertEqual(orders,[])
        self.assertEqual(waits,[])
        self.assertTrue(all(h["reason"]=="PAGINATION_DRIFT_OR_INVALID"
                            for h in health.values()))

    def test_missing_token_never_contacts_worker(self):
        def forbidden(*args,**kwargs):
            raise AssertionError("network request was not expected")
        output,health=all_structure_orders(
            "",structures=STRUCTURES,worker="https://worker.invalid",
            fetch=forbidden)
        self.assertEqual(output,[])
        self.assertTrue(all(h["reason"]=="missing_api_key" for h in health.values()))


if __name__=="__main__":
    unittest.main()
