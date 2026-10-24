"""Offline, read-only audit of quarantined V4 order rows from an existing run.

Uses stored proof rows and exactly the original downloaded public CSV snapshot.
Does not retrieve passwords, open network connections, mutate SQLite, or send mail.
"""
from __future__ import annotations

import argparse
import bz2
import csv
import json
from collections import Counter
from pathlib import Path

MAX_EXAMPLES = 12
MARKET_COLUMNS = (
    "order_id", "type_id", "location_id", "price",
    "volume_remain", "min_volume", "is_buy_order", "range"
)


def summarize(root: Path, run_folder: str | None = None) -> dict:
    root = Path(root).resolve()
    runs = root / "runs"
    if run_folder:
        if Path(run_folder).name != run_folder or run_folder in (".", ".."):
            raise ValueError("INVALID_RUN_FOLDER_NAME")
        folder = runs / run_folder
    else:
        folders = sorted((p for p in runs.iterdir() if p.is_dir()), reverse=True)
        if not folders:
            raise FileNotFoundError("NO_SCAN_RUNS")
        folder = folders[0]
    if not folder.is_dir():
        raise FileNotFoundError("RUN_FOLDER_NOT_FOUND")

    proof_path = folder / "all_proofs.jsonl"
    deep_path = folder / "deep_shadow.json"
    report = json.loads(deep_path.read_text(encoding="utf-8"))
    expected = int(report.get("invalid_public_orders") or 0)
    examples = []
    errors = Counter()
    detected = 0
    with proof_path.open(encoding="utf-8") as source:
        for line in source:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("reason") != "SOURCE_ORDER_INVALID":
                continue
            if row.get("source_lane") != "PUBLIC":
                continue
            detected += 1
            category = str(row.get("error_type") or "UNKNOWN")
            errors[category] += 1
            if len(examples) < MAX_EXAMPLES:
                examples.append({
                    "row_index": int(row["row_index"]),
                    "error_type": category,
                    "error_detail": str(row.get("error_detail") or "")[:100],
                    "order_id_hint": str(row.get("order_id_hint") or "")[:40],
                })

    index_to_example = {item["row_index"]:item for item in examples}
    if index_to_example:
        csv_path = folder / "source" / "market_orders.csv.bz2"
        with bz2.open(csv_path, "rt", encoding="utf-8", newline="") as reader_file:
            reader = csv.DictReader(reader_file)
            last = max(index_to_example)
            for i, source_row in enumerate(reader):
                if i > last:
                    break
                if i not in index_to_example:
                    continue
                # Only public market field values are shown, never local secrets.
                index_to_example[i]["source_fields"] = {
                    name: (str(source_row.get(name, ""))[:80] if name in reader.fieldnames else None)
                    for name in MARKET_COLUMNS
                }

    return {
        "run_folder_name": folder.name,
        "diagnostic_mode": "OFFLINE_READ_ONLY",
        "source_input_integrity": report.get("source_input_integrity"),
        "invalid_public_orders_reported": expected,
        "invalid_structure_orders_reported": int(report.get("invalid_structure_orders") or 0),
        "invalid_public_proofs_found": detected,
        "proof_count_matches_report": detected == expected,
        "error_types": dict(errors),
        "examples": examples,
        "secret_displayed": False,
        "sql_written": False,
        "mail_enabled": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Inspect quarantined source rows without a new scan")
    parser.add_argument("--data-root", type=Path, default=Path.home() / "EVE-V4-Data")
    parser.add_argument("--run-folder", default=None)
    args = parser.parse_args()
    print(json.dumps(summarize(args.data_root, args.run_folder),
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
