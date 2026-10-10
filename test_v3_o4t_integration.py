import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from send_v3_opportunity_mail import CHANNELS
from v3_o4t_resolve import select_prime_structure
from v3_scan_health import channel_healthy
from v3_structure_contract_scanner import total_volume


def payload(*structures):
    return {
        "ok": True,
        "target_system_id": 30004691,
        "structures": list(structures),
    }


def prime(**changes):
    row = dict(
        structure_id=1050123456789,
        solar_system_id=30004691,
        name="O4T-Z5 - Dracarys. Prime (SummerHall)",
        market_pages=23,
        page1_orders=1000,
    )
    row.update(changes)
    return row


class O4TProductionTests(unittest.TestCase):
    def test_only_unique_exact_system_and_prime_can_be_scanned(self):
        chosen = select_prime_structure(payload(prime()))
        self.assertEqual(chosen["structure_id"], 1050123456789)
        self.assertEqual(chosen["system_id"], 30004691)
        with self.assertRaises(RuntimeError):
            select_prime_structure(payload(prime(solar_system_id=30004692)))
        with self.assertRaises(RuntimeError):
            select_prime_structure(payload(prime(name="Other Alliance. Fortizar")))
        with self.assertRaises(RuntimeError):
            select_prime_structure(payload(prime(), prime(structure_id=1050123456790)))
        with self.assertRaises(RuntimeError):
            select_prime_structure({"ok": True, "target_system_id": 30004937, "structures": [prime()]})

    def test_o4t_production_channels_registered_as_formal(self):
        self.assertEqual(CHANNELS["v3-dc-o4t-to-jita"]["id_col"], "type_id")
        self.assertEqual(CHANNELS["v3-dc-o4t-contract"]["id_col"], "contract_id")
        self.assertEqual(CHANNELS["v3-dc-o4t-contract"]["kind"], "structure-contract")

    def test_o4t_freshness_is_independent_of_main_fast_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            manifest = Path(td) / "o4t.json"
            current = datetime.now(timezone.utc)
            obj = {
                "started_epoch": int(current.timestamp()),
                "channels": {
                    "v3-dc-o4t-to-jita": {"status": "ok"},
                    "v3-dc-o4t-contract": {"status": "ok"},
                },
            }
            manifest.write_text(json.dumps(obj), encoding="utf-8")
            with patch("v3_scan_health.O4T_HEALTH", manifest):
                self.assertTrue(channel_healthy("v3-dc-o4t-to-jita", require_manifest=True))
                self.assertTrue(channel_healthy("v3-dc-o4t-contract", require_manifest=True))
                obj["channels"]["v3-dc-o4t-contract"]["status"] = "failed"
                manifest.write_text(json.dumps(obj), encoding="utf-8")
                self.assertFalse(channel_healthy("v3-dc-o4t-contract", require_manifest=True))
                obj["started_epoch"] = int((current - timedelta(hours=5)).timestamp())
                manifest.write_text(json.dumps(obj), encoding="utf-8")
                self.assertFalse(channel_healthy("v3-dc-o4t-to-jita", require_manifest=True))

    def test_incomplete_contract_volume_is_never_zero_cost(self):
        self.assertIsNone(total_volume({1: 3, 2: 5}, {1: {"packaged_volume": 2.0}}))
        self.assertIsNone(total_volume({1: 3}, {1: {"volume": 0}}))
        self.assertIsNone(total_volume({1: 3}, {1: {"volume": float("inf")}}))
        self.assertEqual(total_volume({1: 3, 2: 5}, {
            1: {"packaged_volume": 2.0},
            2: {"packaged_volume": 0.5},
        }), 8.5)


if __name__ == "__main__":
    unittest.main()
