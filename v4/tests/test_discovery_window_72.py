"""72-scan-window regressions for first-discovery ordering."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from v4.discovery_history import first_seen, market_key, INDEX

JITA = 60003760
SOURCE = 1049588174021


def lead(item_id):
    return {
        "kind": "market", "model_candidate": True,
        "source_location": SOURCE, "type_id": item_id,
        "destination_location": JITA, "valuation_location_id": JITA,
        "valuation_basis": "JITA_4_4_BUY_DEPTH_SNAPSHOT_NOT_LIVE",
    }


def run_folder(root, n, rows):
    stamp = (datetime(2026, 10, 28, tzinfo=timezone.utc) + timedelta(minutes=n)).strftime("%Y%m%dT%H%M%SZ")
    folder = root / "runs" / ("%s-%08d" % (stamp, n))
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_text(
        json.dumps({"status": "SHADOW_RECORDED"}), encoding="utf-8")
    (folder / "all_proofs.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return folder


class WindowDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "runs").mkdir()

    def test_older_than_72_discovery_is_forgotten(self):
        run_folder(self.root, 0, [lead(34)])
        for n in range(1, 72):
            run_folder(self.root, n, [])
        newest = run_folder(self.root, 72, [lead(34), lead(35)])
        seen = first_seen(self.root, newest.name)
        key = market_key(lead(34))
        self.assertEqual(seen[key], "2026-10-28T01:12:00Z")
        index = json.loads((self.root / INDEX).read_text("utf-8"))
        self.assertEqual(index["schema"], 2)
        self.assertEqual(len(index["run_keys"]), 72)
        self.assertNotIn("20261028T000000Z-00000000", index["run_keys"])

    def test_second_same_run_is_idempotent(self):
        older = run_folder(self.root, 1, [lead(34)])
        self.assertEqual(first_seen(self.root, older.name),
                         first_seen(self.root, older.name))

    def test_v1_lifetime_index_migrates_without_retaining_old_seen(self):
        path = self.root / INDEX
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "schema": 1, "last_run": "20200101T000000Z",
            "seen": {market_key(lead(34)): "2020-01-01T00:00:00Z"}
        }), encoding="utf-8")
        folder = run_folder(self.root, 1, [lead(34)])
        seen = first_seen(self.root, folder.name)
        self.assertEqual(seen[market_key(lead(34))],
                         "2026-10-28T00:01:00Z")
        self.assertEqual(json.loads(path.read_text("utf-8"))["schema"], 2)

    def test_bad_v2_index_refuses_to_silently_overwrite(self):
        path = self.root / INDEX
        path.parent.mkdir(parents=True)
        path.write_text('{"schema":2,"last_run":7,"run_keys":{}}',
                        encoding="utf-8")
        folder = run_folder(self.root, 1, [lead(34)])
        with self.assertRaisesRegex(RuntimeError, "DISCOVERY_INDEX_INVALID"):
            first_seen(self.root, folder.name)


if __name__ == "__main__":
    unittest.main()
