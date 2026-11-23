"""Progress diagnostics must reveal stalled pages without leaking API keys or orders."""
import unittest

from v4.structure_transport import all_structure_orders


class PrivateMarketProgressTests(unittest.TestCase):
    def scan(self, fetch, *, attempts=3, progress=None):
        return all_structure_orders(
            "TOP_SECRET_KEY", structures={"cj": (222, "dc")},
            worker="https://example.invalid", fetch=fetch,
            sleep=lambda _: None, jitter=lambda: 0.0,
            page_attempts=attempts, pace_seconds=0, progress=progress)

    def test_emits_page_attempts_and_success_without_secrets(self):
        lines = []
        def fake(url, params, headers, timeout):
            self.assertEqual(headers["Authorization"], "Bearer TOP_SECRET_KEY")
            self.assertEqual(timeout, (10,55))
            p=params["page"]
            return {"ok": True, "structure_id": 222, "page": p, "pages": 2,
                    "orders": [{"order_id": 9000+p, "private": "ORDER_SECRET"}]}, {}
        orders, health = self.scan(fake, progress=lines.append)
        self.assertEqual(health["cj"]["status"], "COMPLETE")
        self.assertEqual(len(orders), 2)
        self.assertEqual(sum("STRUCTURE_REQUEST_START" in s for s in lines),2)
        self.assertEqual(sum("STRUCTURE_REQUEST_OK" in s for s in lines),2)
        self.assertTrue(any("STRUCTURE_LANE_COMPLETE lane=cj pages=2" in s for s in lines))
        self.assertNotIn("TOP_SECRET_KEY", "\n".join(lines))
        self.assertNotIn("ORDER_SECRET", "\n".join(lines))
        self.assertNotIn("example.invalid", "\n".join(lines))

    def test_retry_errors_report_exception_class_not_exception_message(self):
        lines = []
        attempts = 0
        def fake(url, params, headers, timeout):
            nonlocal attempts
            attempts += 1
            raise TimeoutError("SENSITIVE_CONTENT_MUST_NOT_LEAK")
        orders, health = self.scan(fake, attempts=3, progress=lines.append)
        self.assertEqual(orders, [])
        self.assertEqual(health["cj"]["reason"], "TRANSIENT_EXHAUSTED")
        self.assertEqual(health["cj"]["transient_retries"],2)
        self.assertEqual(sum("STRUCTURE_REQUEST_ERROR" in s for s in lines),3)
        self.assertTrue(any("exception=TimeoutError http_status=none" in s for s in lines))
        self.assertTrue(any("STRUCTURE_LANE_FAILED" in s for s in lines))
        self.assertNotIn("SENSITIVE_CONTENT", "\n".join(lines))

    def test_progress_callback_failure_never_alters_market_result(self):
        def bad(_):
            raise RuntimeError("logging failed")
        def fake(url, params, headers, timeout):
            return {"ok":True,"structure_id":222,"page":1,"pages":1,
                    "orders":[{"order_id":1}]}, {}
        orders, health = self.scan(fake,progress=bad)
        self.assertEqual([x["order_id"] for x in orders],[1])
        self.assertEqual(health["cj"]["status"],"COMPLETE")

    def test_no_logging_callback_preserves_existing_behavior(self):
        def fake(url, params, headers, timeout):
            return {"ok":True,"structure_id":222,"page":1,"pages":1,
                    "orders":[]}, {}
        orders, health = self.scan(fake)
        self.assertEqual(orders,[])
        self.assertEqual(health["cj"]["status"],"COMPLETE")


if __name__ == "__main__":
    unittest.main()
