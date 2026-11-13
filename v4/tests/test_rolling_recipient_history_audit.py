"""Read-only historical game mail audit cannot unlock rolling72 deletions."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from v4 import rolling_recipient_history_audit as mod
from v4.game_mail_review import EXPECTED_SENDER_ID

FOLDER = "20261014T124407Z-502455f5"
MIKE = 2124493042
LADY = 2124729692


class HistoricalReceiptAuditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "mail-review" / "eve-receipts").mkdir(parents=True)
        (self.root / "mail-review" / "receipts").mkdir(parents=True)

    def receipt(self, name, ident, *, filename=None, sender=EXPECTED_SENDER_ID,
                timestamp="2026-10-14T12:55:00+00:00", source=mod.OFFICIAL_SOURCE):
        row = dict(run=FOLDER, recipient=name, recipient_id=ident,
                   confirmed_at=timestamp, sender_id=sender, source=source,
                   mail_id=4001, research_only=True)
        path = (self.root / "mail-review" / "eve-receipts" /
                (filename or FOLDER + "-" + str(ident) + ".json"))
        path.write_text(json.dumps(row), encoding="utf-8")
        return path

    def gmail(self):
        path = (self.root / "mail-review" / "receipts" /
                (FOLDER + ".json"))
        path.write_text(json.dumps(
            {"run": FOLDER, "sent_at": "2026-10-14T13:00:00Z"}))

    def test_worker_dual_legacy_receipts_are_evidence_not_authorization(self):
        # Old canonical format lacks display name, but has exact verified ID.
        self.receipt(None, MIKE, filename=FOLDER + ".json")
        self.receipt("LadyBaBa", LADY)
        self.gmail()
        before = sorted(str(p)+":"+p.read_text()
                        for p in self.root.rglob("*.json"))
        result = mod.audit_folders(self.root, [FOLDER])
        after = sorted(str(p)+":"+p.read_text()
                       for p in self.root.rglob("*.json"))
        self.assertEqual(result["worker_receipt_coverage"][
            "BOTH_LEGACY_WORKER_RECEIPTS"], 1)
        self.assertEqual(result["lady_recipient_ids_observed"], {str(LADY): 1})
        self.assertFalse(result["permitted_to_delete"])
        self.assertFalse(result["proves_historical_recipient_policy"])
        self.assertFalse(result["modified"])
        self.assertEqual(before, after)

    def test_missing_lady_remains_blocked_and_gmail_missing_reported(self):
        self.receipt(None, MIKE, filename=FOLDER + ".json")
        result = mod.audit_folders(self.root, [FOLDER])
        self.assertEqual(result["worker_receipt_coverage"]["MIKE_ONLY"], 1)
        self.assertEqual(result["worker_receipt_coverage"]["NO_GMAIL_RECEIPT"], 1)
        self.assertEqual(len(result["nondual_examples"]), 1)
        self.assertFalse(result["permitted_to_delete"])

    def test_mismatched_sender_and_unverified_source_not_counted(self):
        self.receipt(None, MIKE, filename=FOLDER + ".json", sender=999)
        self.receipt("LadyBaBa", LADY, source="USER_WRITTEN_NOT_EVE")
        result = mod.audit_folders(self.root, [FOLDER])
        self.assertEqual(result["worker_receipt_coverage"]["NEITHER"], 1)
        self.assertEqual(result["invalid_or_unverifiable_receipts"], 2)

    def test_receipt_before_run_is_rejected(self):
        self.receipt(None, MIKE, filename=FOLDER + ".json",
                     timestamp="2026-10-14T12:01:00+00:00")
        result = mod.audit_folders(self.root, [FOLDER])
        self.assertEqual(result["worker_receipt_coverage"]["NEITHER"], 1)
        self.assertEqual(result["invalid_or_unverifiable_receipts"], 1)

    def test_wrong_id_for_mike_is_not_accepted(self):
        self.receipt("MikeChong", 12345, filename=FOLDER + ".json")
        result = mod.audit_folders(self.root, [FOLDER])
        self.assertEqual(result["worker_receipt_coverage"]["NEITHER"], 1)
        self.assertEqual(result["invalid_or_unverifiable_receipts"], 1)


if __name__ == "__main__":
    unittest.main()
