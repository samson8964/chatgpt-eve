"""Opt-in V4 game-mail contract research digest; never a trade execution signal.

The existing Cloudflare mail Worker was already tested end-to-end by
LadyGuaGua -> MikeChong (ESI mail ID 403312040). This module only queues
a digest after the local V4 snapshot is DURABLY recorded. All valuations
must be Jita 4-4 buy-depth snapshots and are explicitly not live verified.

No secret in a config file, mail body, receipt or console. No schedule is
installed or switched on at import time. The user opts in explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from v4.contract_review import make_review
from v4.eve_mail_test import (
    WORKER_URL, EXPECTED_SENDER, GameMailTestError,
    _get_bridge_credential, _request_json,
)
from v4.research_mail import render_review

SETTINGS_FILE = Path("config/eve_game_mail_review.json")
RECEIPTS = Path("mail-review/eve-receipts")
# Recipient identity established by user-visible EVE API success AND inbox check.
ALLOWED_RECIPIENTS = {"MikeChong": 2124493042}
EXPECTED_SENDER_ID = 2124679425


def _write_atomic(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    try:
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def enable(root: Path, *, recipient: str = "MikeChong") -> dict:
    if recipient not in ALLOWED_RECIPIENTS:
        raise ValueError("EVE_MAIL_RECIPIENT_NOT_VERIFIED")
    _write_atomic(Path(root) / SETTINGS_FILE, {
        "schema": 1, "enabled": True, "mode": "V4_RESEARCH_ONLY",
        "sender": EXPECTED_SENDER, "recipient": recipient,
        "recipient_id": ALLOWED_RECIPIENTS[recipient],
        "valuation_location_id": 60003760,
    })
    return {"status": "V4_GAME_RESEARCH_MAIL_ENABLED",
            "recipient": recipient, "recipient_id": ALLOWED_RECIPIENTS[recipient],
            "automatic_trade_alerts": False, "sent": False}


def disable(root: Path) -> dict:
    _write_atomic(Path(root) / SETTINGS_FILE, {
        "schema": 1, "enabled": False, "mode": "V4_RESEARCH_ONLY"})
    return {"status": "V4_GAME_RESEARCH_MAIL_DISABLED", "sent": False}


def read_settings(root: Path) -> dict | None:
    path = Path(root) / SETTINGS_FILE
    if not path.is_file():
        return None
    config = json.loads(path.read_text(encoding="utf-8"))
    if config.get("schema") != 1 or config.get("mode") != "V4_RESEARCH_ONLY":
        raise GameMailTestError("V4_GAME_MAIL_CONFIG_INVALID")
    if config.get("enabled") is False:
        return None
    recipient = config.get("recipient")
    if (config.get("enabled") is not True or
            config.get("sender") != EXPECTED_SENDER or
            recipient not in ALLOWED_RECIPIENTS or
            config.get("recipient_id") != ALLOWED_RECIPIENTS[recipient] or
            config.get("valuation_location_id") != 60003760):
        raise GameMailTestError("V4_GAME_MAIL_CONFIG_INVALID")
    return config


def compact_digest(review: dict) -> tuple[str, str]:
    """Bounded text without altering review evidence or claiming live offers."""
    # EVE Worker enforces max 10,000 characters. Reserve room for truncation.
    limited = dict(review)
    limited["research_leads"] = list(review.get("research_leads") or [])[:5]
    subject, body = render_review(limited)
    subject = subject.replace("非交易提醒", "快照研究·不可直接买入")
    if len(body) > 9000:
        head = body[:8600].rsplit("\n", 1)[0]
        body = head + "\n[本轮信息过长，已截断；完整证明保存在本机 SQLite 和扫描文件。]"
    return subject[:180], body


def send_review_to_game(root: Path, *, expected_run: str | None = None,
                        session=None, get_key=None) -> dict:
    root = Path(root)
    config = read_settings(root)
    if config is None:
        return {"status": "V4_GAME_RESEARCH_MAIL_DISABLED", "sent": False}
    review = make_review(root)
    run_name = review["run_folder"]
    if expected_run is not None and expected_run != run_name:
        raise GameMailTestError("GAME_MAIL_LATEST_RUN_MISMATCH")
    if review.get("contract_pricing_basis") != "JITA_4_4_BUY_DEPTH_SNAPSHOT":
        raise GameMailTestError("GAME_MAIL_NON_JITA_PRICING_FORBIDDEN")
    receipt = root / RECEIPTS / (run_name + ".json")
    if receipt.exists():
        return {"status": "V4_GAME_RESEARCH_MAIL_ALREADY_SENT",
                "sent": False, "run_folder_name": run_name}

    from requests import Session
    client = session if session is not None else Session()
    key = _get_bridge_credential(get_key)
    headers = {"Authorization": "Bearer " + key,
               "User-Agent": "EVE V4 research-review local service"}
    code, health = _request_json(
        client, "GET", WORKER_URL + "/api/mail-health", headers=headers, timeout=30)
    if code == 401:
        raise GameMailTestError("GAME_MAIL_BRIDGE_API_KEY_MISMATCH")
    if code == 409:
        raise GameMailTestError("GAME_MAIL_SENDER_AUTH_EXPIRED")
    if (code != 200 or health.get("ok") is not True or
            health.get("sender_name") != EXPECTED_SENDER or
            health.get("sender_id") != EXPECTED_SENDER_ID):
        raise GameMailTestError("GAME_MAIL_SENDER_NOT_VERIFIED")

    subject, body = compact_digest(review)
    recipient_id = config["recipient_id"]
    identity = (run_name + "|" + str(recipient_id) +
                "|JITA_4_4_BUY_DEPTH_SNAPSHOT")
    idem = "v4-contract-research:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:38]
    code, response = _request_json(
        client, "POST", WORKER_URL + "/api/send-mail",
        headers={**headers, "Content-Type": "application/json"},
        json={"recipient_id": recipient_id, "subject": subject,
              "body": body, "idempotency_key": idem}, timeout=80)
    if code != 200 or response.get("ok") is not True:
        raise GameMailTestError("GAME_MAIL_WORKER_REJECTED_HTTP_" + str(code))
    skipped = response.get("skipped") is True
    mail_id = None
    if not skipped:
        try:
            mail_id = int(response.get("mail_id"))
            if mail_id <= 0:
                raise ValueError("invalid id")
            if (response.get("sender_id") != EXPECTED_SENDER_ID or
                    response.get("recipient_id") != recipient_id):
                raise ValueError("identity mismatch")
        except (ValueError, TypeError, OverflowError):
            raise GameMailTestError("GAME_MAIL_RECEIPT_INCONSISTENT") from None
    elif response.get("reason") != "duplicate":
        raise GameMailTestError("GAME_MAIL_WORKER_SKIP_UNEXPLAINED")

    _write_atomic(receipt, {
        "schema": 1, "run": run_name,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
        "source": "EVE_OFFICIAL_MAIL_VIA_EXISTING_WORKER",
        "sender_id": EXPECTED_SENDER_ID, "recipient_id": recipient_id,
        "mail_id": mail_id, "already_accepted": skipped,
        "valuation_basis": "JITA_4_4_BUY_DEPTH_SNAPSHOT",
        "research_only": True, "formal_trade_alert": False,
    })
    return {"status": ("V4_GAME_RESEARCH_MAIL_ALREADY_ACCEPTED"
                       if skipped else "V4_GAME_RESEARCH_MAIL_SENT"),
            "sent": not skipped, "run_folder_name": run_name,
            "recipient": config["recipient"], "recipient_id": recipient_id,
            "mail_id": mail_id, "research_only": True,
            "formal_trade_alert": False,
            "research_leads_total": review.get("research_leads_total", 0)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Opt-in V4 EVE game-mail review digest")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--enable", action="store_true")
    group.add_argument("--disable", action="store_true")
    group.add_argument("--send-now", action="store_true")
    group.add_argument("--status", action="store_true")
    parser.add_argument("--data-root", type=Path, default=Path.home()/"EVE-V4-Data")
    parser.add_argument("--recipient", choices=tuple(ALLOWED_RECIPIENTS), default="MikeChong")
    args = parser.parse_args()
    try:
        if args.enable:
            result = enable(args.data_root, recipient=args.recipient)
        elif args.disable:
            result = disable(args.data_root)
        elif args.status:
            config = read_settings(args.data_root)
            result = {"status": "V4_GAME_RESEARCH_MAIL_ENABLED" if config else
                      "V4_GAME_RESEARCH_MAIL_DISABLED", "sent": False,
                      "recipient": (config or {}).get("recipient")}
        else:
            result = send_review_to_game(args.data_root)
    except (GameMailTestError, ValueError, OSError) as exc:
        print(json.dumps({"status": "V4_GAME_RESEARCH_MAIL_FAILED",
                          "sent": False, "error_type": type(exc).__name__,
                          "reason": str(exc)}, ensure_ascii=False))
        raise SystemExit(4) from None
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
