"""Real-failure regressions: C-J page-count drift and UALX-3 exhausted resets.

Uses a fake Worker; never contacts ESI or prints any secrets.
"""
import unittest

from v4.structure_transport import all_structure_orders


class StructureRecoveryTests(unittest.TestCase):
    def scan(self, fetch, *, attempts=3, restart_limit=1):
        waits=[]
        orders,health=all_structure_orders(
            "secret-is-never-printed",
            structures={"cj":(222,"dc")},worker="https://example.invalid",
            fetch=fetch,sleep=waits.append,jitter=lambda:0.,
            page_attempts=attempts,pace_seconds=0,
            pagination_restart_limit=restart_limit)
        return orders,health["cj"],waits

    def test_changed_page_count_restarts_whole_book_once(self):
        first_pages=0
        visited=[]
        def fetch(_url,params,_headers=None,**kwargs):
            nonlocal first_pages
            page=params["page"]
            if page==1:
                first_pages+=1
            visited.append((first_pages,page))
            # Epoch 1: page count changed on page 2; old page 1 must
            # NEVER be combined with epoch 2 page 2.
            total=3 if (first_pages==1 and page==2) else 2
            return ({"ok":True,"structure_id":222,"page":page,
                     "pages":total,"orders":[{"order_id":first_pages*100+page}]}, {})
        orders,h,_=self.scan(fetch)
        self.assertEqual(h["status"],"COMPLETE")
        self.assertEqual(h["pages_fetched"],2)
        self.assertEqual(h["pagination_restarts"],1)
        self.assertEqual([x["order_id"] for x in orders],[201,202])
        self.assertEqual(visited,[(1,1),(1,2),(2,1),(2,2)])

    def test_repeated_page_count_drift_keeps_lane_failed_and_empty(self):
        def fetch(_url,params,**kwargs):
            p=params["page"]
            return ({"ok":True,"structure_id":222,"page":p,
                     "pages":3 if p==2 else 2,
                     "orders":[{"order_id":p}]}, {})
        orders,h,_=self.scan(fetch)
        self.assertEqual(orders,[])
        self.assertEqual(h["status"],"FAILED")
        self.assertEqual(h["reason"],"PAGINATION_DRIFT_OR_INVALID")
        self.assertTrue(h["page_count_changed"])
        self.assertEqual(h["pagination_restarts"],1)
        self.assertEqual(h["pages_fetched"],1)

    def test_invalid_page_payload_fails_closed_without_restart(self):
        visited=[]
        def fetch(_url,params,**kwargs):
            p=params["page"]
            visited.append(p)
            return ({"ok":True,"structure_id":333 if p==2 else 222,
                     "page":p,"pages":2,"orders":[{"order_id":p}]}, {})
        orders,h,_=self.scan(fetch)
        self.assertEqual(orders,[])
        self.assertEqual(visited,[1,2])
        self.assertEqual(h["pagination_restarts"],0)
        self.assertEqual(h["reason"],"PAGINATION_DRIFT_OR_INVALID")
        self.assertFalse(h["page_count_changed"])

    def test_exhaustion_counts_failed_page_retries_and_sanitizes_error(self):
        calls=[]
        def fetch(_url,params,**kwargs):
            p=params["page"]
            calls.append(p)
            if p==2:
                raise ConnectionResetError(10054,"secret-is-never-printed")
            return ({"ok":True,"structure_id":222,"page":p,
                     "pages":2,"orders":[{"order_id":p}]}, {})
        orders,h,waits=self.scan(fetch,attempts=5)
        self.assertEqual(orders,[])
        self.assertEqual(calls,[1,2,2,2,2,2])
        self.assertEqual(len(waits),4)
        self.assertEqual(h["reason"],"TRANSIENT_EXHAUSTED")
        self.assertEqual(h["failed_page"],2)
        self.assertEqual(h["attempts_on_failed_page"],5)
        self.assertEqual(h["transient_retries"],4)
        self.assertEqual(h["request_exception_class"],"ConnectionResetError")
        self.assertEqual(h["pagination_restarts"],0)
        self.assertNotIn("secret-is-never-printed",str(h))

    def test_authorization_denial_is_never_restarted(self):
        visited=[]
        class Forbidden(Exception):
            def __init__(self):
                self.response=type("Response",(),{"status_code":403})()
        def fetch(_url,params,**kwargs):
            visited.append(params["page"])
            raise Forbidden()
        orders,h,waits=self.scan(fetch)
        self.assertEqual(orders,[])
        self.assertEqual(visited,[1])
        self.assertEqual(waits,[])
        self.assertEqual(h["reason"],"NONRETRYABLE_REQUEST")
        self.assertEqual(h["http_status"],403)
        self.assertEqual(h["pagination_restarts"],0)


if __name__=="__main__":
    unittest.main()
