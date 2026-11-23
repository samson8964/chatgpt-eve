"""Offline, single-writer V4 SQLite shadow ledger.

This module has no mail sender, external HTTP, or ESI permissions. Every proof
is revalidated and reconciled in one transaction. It cannot activate mail.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

INSTANCE = re.compile(r"^[A-Za-z0-9:_-]{8,160}$")
RUN = re.compile(r"^[A-Za-z0-9_-]{5,128}$")
ALLOWED = frozenset(("WATCH", "RESEARCH"))


def _invalid_constant(token: str):
    raise ValueError("NONFINITE_JSON_TOKEN:" + token)


def _json(text: str):
    return json.loads(text, parse_constant=_invalid_constant)


def _dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":"))


def _init(conn: sqlite3.Connection):
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS scan_runs (
            run_id TEXT PRIMARY KEY, status TEXT NOT NULL,
            proof_count INTEGER NOT NULL, proof_sha256 TEXT NOT NULL,
            report_json TEXT NOT NULL, audited_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS proof_versions (
            run_id TEXT NOT NULL, instance TEXT NOT NULL,
            status TEXT NOT NULL, reason TEXT NOT NULL,
            proof_json TEXT NOT NULL,
            PRIMARY KEY (run_id, instance),
            FOREIGN KEY (run_id) REFERENCES scan_runs(run_id)
        );
        CREATE INDEX IF NOT EXISTS idx_proof_status ON proof_versions(status);
    """)


def persist(db_path: Path, report_path: Path, proof_path: Path) -> dict:
    db_path, report_path, proof_path = map(Path, (db_path, report_path, proof_path))
    if not proof_path.is_file() or not report_path.is_file():
        raise ValueError("MISSING_SHADOW_ARTIFACT")
    report = _json(report_path.read_text(encoding="utf-8"))
    if report.get("status") != "SHADOW_ONLY_NO_LIVE_ALERTS" or report.get("formal_candidates") != 0:
        raise ValueError("NON_SHADOW_REPORT_OR_MAIL_CANDIDATES")
    run_id = report.get("run_id")
    if not isinstance(run_id, str) or not RUN.fullmatch(run_id):
        raise ValueError("INVALID_RUN_ID")
    expected = report.get("proof_count")
    if isinstance(expected, bool) or not isinstance(expected, int) or expected <= 0:
        raise ValueError("INVALID_PROOF_COUNT")
    digest = hashlib.sha256()
    reasons = Counter()
    statuses = Counter()
    models = 0
    count = 0
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        _init(conn)
        conn.execute("BEGIN IMMEDIATE")
        previous = conn.execute(
            "SELECT proof_sha256, proof_count FROM scan_runs WHERE run_id=?",
            (run_id,)).fetchone()
        # Existing runs may be audited again, never silently revised.
        if not previous:
            conn.execute(
                "INSERT INTO scan_runs VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, "IMPORTING", expected, "PENDING", _dump(report),
                 datetime.now(timezone.utc).isoformat()))
        with proof_path.open("rb") as stream:
            for lineno, raw in enumerate(stream, start=1):
                digest.update(raw)
                if not raw.strip():
                    continue
                proof = _json(raw.decode("utf-8"))
                if not isinstance(proof, dict):
                    raise ValueError("INVALID_PROOF_TYPE")
                instance = proof.get("instance") or proof.get("family")
                if not isinstance(instance, str) or not INSTANCE.fullmatch(instance):
                    raise ValueError("INVALID_PROOF_INSTANCE_LINE:" + str(lineno))
                status = proof.get("status")
                if status not in ALLOWED:
                    raise ValueError("UNSAFE_SHADOW_PROOF_STATUS:" + str(lineno))
                reason = proof.get("reason")
                if not isinstance(reason, str) or not reason:
                    raise ValueError("MISSING_PROOF_REASON:" + str(lineno))
                proof["instance"] = instance
                data = _dump(proof)
                models += proof.get("model_candidate") is True
                count += 1
                reasons[reason] += 1
                statuses[status] += 1
                old = conn.execute(
                    "SELECT proof_json FROM proof_versions WHERE run_id=? AND instance=?",
                    (run_id, instance)).fetchone()
                if old:
                    if old[0] != data or not previous:
                        raise ValueError("DUPLICATE_OR_CONFLICTING_PROOF:" + instance)
                else:
                    if previous:
                        raise ValueError("PREEXISTING_RUN_MISSING_PROOF:" + instance)
                    conn.execute(
                        "INSERT INTO proof_versions VALUES (?,?,?,?,?)",
                        (run_id, instance, status, reason, data))
        sha = digest.hexdigest()
        if count != expected:
            raise ValueError("ARTIFACT_COUNT_MISMATCH")
        if dict(reasons) != report.get("reason_counts"):
            raise ValueError("REASON_HISTOGRAM_MISMATCH")
        if models != report.get("model_candidates"):
            raise ValueError("MODEL_CANDIDATE_COUNT_MISMATCH")
        if previous and tuple(previous) != (sha, expected):
            raise ValueError("RUN_ID_REUSED_WITH_DIFFERENT_ARTIFACT")
        actual = conn.execute(
            "SELECT COUNT(*) FROM proof_versions WHERE run_id=?",
            (run_id,)).fetchone()[0]
        stored_reasons = dict(conn.execute(
            "SELECT reason, COUNT(*) FROM proof_versions WHERE run_id=? GROUP BY reason",
            (run_id,)).fetchall())
        stored_status = dict(conn.execute(
            "SELECT status, COUNT(*) FROM proof_versions WHERE run_id=? GROUP BY status",
            (run_id,)).fetchall())
        if actual != count or stored_reasons != dict(reasons) or stored_status != dict(statuses):
            raise ValueError("SQL_ROW_OR_HISTOGRAM_MISMATCH")
        if not previous:
            conn.execute("UPDATE scan_runs SET status=?, proof_sha256=? WHERE run_id=?",
                         ("SHADOW_VERIFIED_OFFLINE", sha, run_id))
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"ok": True, "run_id": run_id, "sqlite_unique_proofs": count,
            "proofs_sha256": sha, "reason_counts": dict(reasons),
            "status_counts": dict(statuses), "model_candidates": models,
            "shadow_only": True, "mail_enabled": False,
            "live_esi_validated": False, "ready_for_production": False,
            "database": "LOCAL_SQLITE"}


def main():
    p = argparse.ArgumentParser(description="Offline shadow-only V4 SQLite import")
    p.add_argument("--db", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--proofs", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(persist(args.db, args.report, args.proofs), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
