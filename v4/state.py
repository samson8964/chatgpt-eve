"""V4 durable event ledger for single-writer SQLite environments.

Explicitly NOT a deployment-ready distributed Outbox: deploy production only
after Cloudflare D1 or equivalent shared transactional persistence is provisioned.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


class Ledger:
    def __init__(self, path: str):
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.execute('pragma busy_timeout=30000')
        self.connection.execute('pragma journal_mode=WAL')
        self.connection.executescript('''
            CREATE TABLE IF NOT EXISTS scan_runs (
                run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL,
                source_coverage TEXT NOT NULL, status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS proof_versions (
                run_id TEXT NOT NULL, instance TEXT NOT NULL, proof TEXT NOT NULL,
                PRIMARY KEY(run_id, instance));
            CREATE TABLE IF NOT EXISTS outbox (
                instance TEXT NOT NULL, channel TEXT NOT NULL, recipient TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'pending',
                first_run TEXT NOT NULL, last_error TEXT,
                PRIMARY KEY(instance, channel, recipient));
        ''')
        self.connection.commit()

    def record_run(self, run_id: str, coverage: dict, status: str) -> None:
        with self.connection:
            self.connection.execute('INSERT INTO scan_runs VALUES (?, ?, ?, ?)',
                (run_id, datetime.now(timezone.utc).isoformat(), json.dumps(coverage), status))

    def record_proofs(self, run_id: str, proofs: list[dict]) -> int:
        """ALL proof rows are recorded, whether prior alerts exist or not."""
        with self.connection:
            for row in proofs:
                self.connection.execute(
                    'INSERT OR REPLACE INTO proof_versions VALUES (?, ?, ?)',
                    (run_id, row['instance'] or row['family'],
                     json.dumps(row, default=str, sort_keys=True)))
        return len(proofs)

    def enqueue(self, run_id: str, proofs: list[dict], recipients: list[str],
                *, channel: str = 'eve') -> int:
        added = 0
        with self.connection:
            for row in proofs:
                if row.get('status') != 'MAIL' or not row.get('instance'):
                    continue
                for recipient in recipients:
                    cur = self.connection.execute(
                        'INSERT OR IGNORE INTO outbox(instance, channel, recipient, first_run) VALUES (?, ?, ?, ?)',
                        (row['instance'], channel, recipient, run_id))
                    added += cur.rowcount
        return added

    def pending(self, recipient: str) -> list[str]:
        return [r[0] for r in self.connection.execute(
            "SELECT instance FROM outbox WHERE recipient=? AND state='pending' ORDER BY instance",
            (recipient,))]

    def mark_sent(self, instance: str, recipient: str, *, channel: str = 'eve'):
        with self.connection:
            self.connection.execute(
                "UPDATE outbox SET state='sent' WHERE instance=? AND channel=? AND recipient=?",
                (instance, channel, recipient))

    def close(self):
        self.connection.close()
