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

from v4.unified_review import make_review, render as render_unified
from v4.eve_mail_test import (
    WORKER_URL, EXPECTED_SENDER, GameMailTestError,
    _get_bridge_credential, _request_json, _resolve_recipient,
)
# Both mail channels share the same compact, link-aware formatter.

SETTINGS_FILE = Path("config/eve_game_mail_review.json")
RECEIPTS = Path("mail-review/eve-receipts")
# Recipient identity established by user-visible EVE API success AND inbox check.
ALLOWED_RECIPIENTS = {"MikeChong": 2124493042}
USER_APPROVED = ("MikeChong", "LadyBaBa")
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
    """Accept existing single-recipient configs and new two-recipient format."""
    path = Path(root) / SETTINGS_FILE
    if not path.is_file():
        return None
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError):
        raise GameMailTestError("V4_GAME_MAIL_CONFIG_INVALID") from None
    if not isinstance(config, dict) or config.get("mode") != "V4_RESEARCH_ONLY":
        raise GameMailTestError("V4_GAME_MAIL_CONFIG_INVALID")
    if config.get("enabled") is False and config.get("schema") in (1, 2):
        return None
    if (config.get("enabled") is not True or
            config.get("sender") != EXPECTED_SENDER or
            config.get("valuation_location_id") != 60003760):
        raise GameMailTestError("V4_GAME_MAIL_CONFIG_INVALID")
    if config.get("schema") == 1:
        name, ident = config.get("recipient"), config.get("recipient_id")
        rows = [{"name": name, "id": ident}]
        if name not in ALLOWED_RECIPIENTS:
            raise GameMailTestError("V4_GAME_MAIL_CONFIG_INVALID")
    elif config.get("schema") == 2:
        rows = config.get("recipients")
        if not isinstance(rows, list) or not (1 <= len(rows) <= 2):
            raise GameMailTestError("V4_GAME_MAIL_CONFIG_INVALID")
    else:
        raise GameMailTestError("V4_GAME_MAIL_CONFIG_INVALID")
    names, ids = set(), set()
    for row in rows:
        if not isinstance(row, dict):
            raise GameMailTestError("V4_GAME_MAIL_CONFIG_INVALID")
        name, ident = row.get("name"), row.get("id")
        if (name not in USER_APPROVED or isinstance(ident, bool) or
                not isinstance(ident, int) or ident <= 0 or
                (name in ALLOWED_RECIPIENTS and ident != ALLOWED_RECIPIENTS[name]) or
                name in names or ident in ids):
            raise GameMailTestError("V4_GAME_MAIL_CONFIG_INVALID")
        names.add(name)
        ids.add(ident)
    return {**config, "recipients": [{"name": row["name"], "id": row["id"]}
                                     for row in rows]}


def add_recipient(root: Path, *, recipient: str = "LadyBaBa",
                  session=None, resolver=None) -> dict:
    """Add LadyBaBa by ESI's exact-name lookup, preserving MikeChong.

    Never replace existing config on failed ESI lookup or changed identity.
    No sender credential needed for public ID lookup, and no mail is sent.
    """
    if recipient not in USER_APPROVED:
        raise ValueError("EVE_MAIL_RECIPIENT_NOT_ALLOWED")
    root = Path(root)
    existing = read_settings(root)
    if existing is None:
        raise GameMailTestError("V4_GAME_MAIL_ENABLE_MIKECHONG_FIRST")
    recipients = list(existing["recipients"])
    for row in recipients:
        if row["name"] == recipient:
            return {"status":"V4_GAME_RECIPIENT_ALREADY_ENABLED",
                    "recipient":recipient, "recipient_id":row["id"],
                    "recipients":[p["name"] for p in recipients], "sent":False}
    if resolver is not None:
        ident = resolver(recipient)
    elif recipient in ALLOWED_RECIPIENTS:
        ident = ALLOWED_RECIPIENTS[recipient]
    else:
        if session is None:
            from requests import Session
            session = Session()
        ident = _resolve_recipient(recipient, session)
    if isinstance(ident, bool) or not isinstance(ident, int) or ident <= 0:
        raise GameMailTestError("EVE_MAIL_RECIPIENT_ID_INVALID")
    recipients.append({"name":recipient, "id":ident})
    if len(recipients) > 2 or len({x["id"] for x in recipients}) != len(recipients):
        raise GameMailTestError("EVE_MAIL_RECIPIENT_ID_INVALID")
    _write_atomic(root / SETTINGS_FILE, {
        "schema":2, "enabled":True, "mode":"V4_RESEARCH_ONLY",
        "sender":EXPECTED_SENDER, "recipients":recipients,
        "valuation_location_id":60003760,
    })
    return {"status":"V4_GAME_RECIPIENT_ADDED", "sent":False,
            "recipient":recipient, "recipient_id":ident,
            "recipients":[row["name"] for row in recipients],
            "formal_alerts_enabled":False}


def compact_digest(review: dict) -> tuple[str, str]:
    """Short EVE in-game rich text with native clickable contract links."""
    subject, body = render_unified(review, game=True)
    # Worker accepts <=10k characters; avoid clipping a <url> markup element.
    if len(body) > 9000:
        raise GameMailTestError("GAME_MAIL_DIGEST_TOO_LONG")
    return subject[:180], body


def _recipient_receipt(root: Path, run_name: str, recipient: dict) -> tuple[Path, ...]:
    # Retain the old MikeChong receipt as his canonical receipt, so an
    # already-sent old run NEVER gets duplicated after this upgrade.
    legacy = root / RECEIPTS / (run_name + ".json")
    named = root / RECEIPTS / (run_name + "-" + str(recipient["id"]) + ".json")
    return (legacy, named) if recipient["name"] == "MikeChong" else (named,)


def _one_game_mail(root: Path, run_name: str, recipient: dict,
                   client, headers: dict, subject: str, body: str) -> dict:
    ident = recipient["id"]
    name = recipient["name"]
    key = (run_name + "|" + str(ident) + "|JITA_4_4_BUY_DEPTH_SNAPSHOT")
    idem = "v4-contract-research:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:38]
    code, response = _request_json(
        client, "POST", WORKER_URL + "/api/send-mail",
        headers={**headers, "Content-Type": "application/json"},
        json={"recipient_id":ident, "subject":subject,
              "body":body, "idempotency_key":idem}, timeout=80)
    if code != 200 or response.get("ok") is not True:
        raise GameMailTestError("GAME_MAIL_WORKER_REJECTED_HTTP_" + str(code))
    skipped = response.get("skipped") is True
    mail_id = None
    if not skipped:
        try:
            mail_id = int(response.get("mail_id"))
            if (mail_id <= 0 or response.get("sender_id") != EXPECTED_SENDER_ID
                    or response.get("recipient_id") != ident):
                raise ValueError("identity mismatch")
        except (TypeError, ValueError, OverflowError):
            raise GameMailTestError("GAME_MAIL_RECEIPT_INCONSISTENT") from None
    elif response.get("reason") != "duplicate":
        raise GameMailTestError("GAME_MAIL_WORKER_SKIP_UNEXPLAINED")
    receipt = _recipient_receipt(root, run_name, recipient)[0]
    _write_atomic(receipt, {
        "schema":2, "run":run_name,
        "confirmed_at":datetime.now(timezone.utc).isoformat(),
        "source":"EVE_OFFICIAL_MAIL_VIA_EXISTING_WORKER",
        "sender_id":EXPECTED_SENDER_ID,
        "recipient":name, "recipient_id":ident, "mail_id":mail_id,
        "already_accepted":skipped,
        "valuation_basis":"JITA_4_4_BUY_DEPTH_SNAPSHOT",
        "research_only":True, "formal_trade_alert":False,
    })
    return {
        "status":("V4_GAME_RESEARCH_MAIL_ALREADY_ACCEPTED" if skipped
                  else "V4_GAME_RESEARCH_MAIL_SENT"),
        "recipient":name, "recipient_id":ident, "sent":not skipped,
        "mail_id":mail_id, "run_folder_name":run_name}


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

    outcomes = []
    pending = []
    for receiver in config["recipients"]:
        if any(p.exists() for p in _recipient_receipt(root, run_name, receiver)):
            outcomes.append({"status":"V4_GAME_RESEARCH_MAIL_ALREADY_SENT",
                             "recipient":receiver["name"], "recipient_id":receiver["id"],
                             "sent":False, "run_folder_name":run_name})
        else:
            pending.append(receiver)
    if pending:
        if session is None:
            from requests import Session
            client = Session()
        else:
            client = session
        key = _get_bridge_credential(get_key)
        headers = {"Authorization":"Bearer " + key,
                   "User-Agent":"EVE V4 research-review local service"}
        code, health = _request_json(
            client, "GET", WORKER_URL + "/api/mail-health", headers=headers, timeout=30)
        if code == 401:
            raise GameMailTestError("GAME_MAIL_BRIDGE_API_KEY_MISMATCH")
        if code == 409:
            raise GameMailTestError("GAME_MAIL_SENDER_AUTH_EXPIRED")
        if (code != 200 or health.get("ok") is not True
                or health.get("sender_name") != EXPECTED_SENDER
                or health.get("sender_id") != EXPECTED_SENDER_ID):
            raise GameMailTestError("GAME_MAIL_SENDER_NOT_VERIFIED")
        subject, body = compact_digest(review)
        for receiver in pending:
            try:
                outcomes.append(_one_game_mail(
                    root, run_name, receiver, client, headers, subject, body))
            except (GameMailTestError, OSError) as exc:
                # Continue to the other recipient, with only sanitized
                # deterministic codes; no tokens/HTTP body in logs.
                error = str(exc) if isinstance(exc, GameMailTestError) else "RECEIPT_WRITE_FAILED"
                outcomes.append({
                    "status":"V4_GAME_RESEARCH_MAIL_RECIPIENT_FAILED",
                    "recipient":receiver["name"],
                    "recipient_id":receiver["id"],
                    "sent":False, "error_code":error,
                    "run_folder_name":run_name,
                })
    if len(outcomes) == 1:
        return {**outcomes[0], "research_only":True, "formal_trade_alert":False,
                "research_leads_total":review.get("research_leads_total",0)}
    failures = sum(p["status"] == "V4_GAME_RESEARCH_MAIL_RECIPIENT_FAILED"
                   for p in outcomes)
    return {
        "status":("V4_GAME_RESEARCH_MAIL_PARTIAL_FAILURE" if failures
                  else "V4_GAME_RESEARCH_MAIL_BATCH_SENT" if any(
                      p["sent"] for p in outcomes)
                  else "V4_GAME_RESEARCH_MAIL_BATCH_ALREADY_SENT"),
        "sent":any(p["sent"] for p in outcomes),
        "run_folder_name":run_name,
        "recipients":{p["recipient"]:p for p in outcomes},
        "recipient_success_count":len(outcomes)-failures,
        "recipient_failure_count":failures,
        "research_only":True, "formal_trade_alert":False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Opt-in V4 EVE game-mail review digest")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--enable", action="store_true")
    group.add_argument("--add-recipient", action="store_true")
    group.add_argument("--disable", action="store_true")
    group.add_argument("--send-now", action="store_true")
    group.add_argument("--status", action="store_true")
    parser.add_argument("--data-root", type=Path, default=Path.home()/"EVE-V4-Data")
    parser.add_argument("--recipient", choices=USER_APPROVED, default="MikeChong")
    args = parser.parse_args()
    try:
        if args.enable:
            result = enable(args.data_root, recipient=args.recipient)
        elif args.add_recipient:
            result = add_recipient(args.data_root, recipient=args.recipient)
        elif args.disable:
            result = disable(args.data_root)
        elif args.status:
            config = read_settings(args.data_root)
            result = {"status": "V4_GAME_RESEARCH_MAIL_ENABLED" if config else
                      "V4_GAME_RESEARCH_MAIL_DISABLED", "sent": False,
                      "recipient": (config or {}).get("recipient"),
                      "recipients": [row["name"] for row in
                                     (config or {}).get("recipients", [])]}
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
