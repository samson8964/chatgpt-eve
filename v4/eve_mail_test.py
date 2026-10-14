"""Explicit one-off EVE Online in-game mail test, separate from Gmail and V4 scans.

Uses the existing Windows Credential Manager bridge credential to authenticate
the existing Cloudflare EVE mail Worker. Only sends upon an explicit CLI call.
Never reads/writes scan outputs, changes cron, or logs credentials.
"""
from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone

WORKER_URL = "https://eve-contract-opener.99617224.workers.dev"
ESI_IDS_URL = "https://esi.evetech.net/latest/universe/ids/?datasource=tranquility"
EXPECTED_SENDER = "LadyGuaGua"
RECIPIENTS = ("MikeChong", "LadyBaBa", "LadyGuaGua")


class GameMailTestError(RuntimeError):
    """Safe error code for logs; remote server content is never displayed."""


def _request_json(session, method, url, *, timeout=20, **kwargs):
    try:
        response = session.request(method, url, timeout=timeout, **kwargs)
        status = int(response.status_code)
        try:
            data = response.json()
        except (TypeError, ValueError):
            data = {}
    except Exception as exc:
        # Do not propagate headers/requests repr with the bridge credential.
        raise GameMailTestError("NETWORK_REQUEST_FAILED_" + type(exc).__name__) from None
    if not isinstance(data, dict):
        data = {}
    return status, data


def _get_bridge_credential(get_key=None) -> str:
    if get_key is None:
        from v4.local_bridge_auth import get_bridge_key
        get_key = get_bridge_key
    from v4.local_bridge_auth import valid_bridge_key
    try:
        key = get_key()
    except Exception:
        raise GameMailTestError("WINDOWS_VAULT_CREDENTIAL_UNAVAILABLE") from None
    if not valid_bridge_key(key):
        raise GameMailTestError("EVE_BRIDGE_KEY_MISSING_OR_INVALID")
    return key


def _resolve_recipient(name: str, session) -> int:
    # ESI universe ID lookup is unauthenticated. Never forward the bridge key.
    status, data = _request_json(
        session, "POST", ESI_IDS_URL, json=[name],
        headers={"Content-Type": "application/json",
                 "User-Agent": "EVE V4 manual mail test"}, timeout=25)
    if status != 200:
        raise GameMailTestError("ESI_CHARACTER_LOOKUP_FAILED_HTTP_" + str(status))
    choices = data.get("characters")
    if not isinstance(choices, list):
        raise GameMailTestError("ESI_CHARACTER_NOT_FOUND")
    ids = []
    for row in choices:
        if isinstance(row, dict) and row.get("name") == name:
            try:
                recipient_id = int(row.get("id"))
                if recipient_id > 0:
                    ids.append(recipient_id)
            except (ValueError, TypeError, OverflowError):
                continue
    if len(set(ids)) != 1:
        raise GameMailTestError("ESI_CHARACTER_NOT_FOUND_OR_AMBIGUOUS")
    return ids[0]


def run_test(recipient: str = "MikeChong", *, session=None, get_key=None,
             now=None, idempotency=None, health_only=False) -> dict:
    if recipient not in RECIPIENTS:
        raise GameMailTestError("RECIPIENT_NOT_ON_OWN_CHARACTER_ALLOWLIST")
    from requests import Session
    client = session if session is not None else Session()
    secret = _get_bridge_credential(get_key)
    auth = {"Authorization": "Bearer " + secret,
            "User-Agent": "EVE V4 manual mail test"}
    status, health = _request_json(
        client, "GET", WORKER_URL + "/api/mail-health",
        headers=auth, timeout=30)
    if status == 401:
        raise GameMailTestError("WORKER_API_KEY_MISMATCH")
    if status == 409 or health.get("error") == "mail_sender_not_authorized":
        raise GameMailTestError("MAIL_SENDER_REAUTHORIZE_REQUIRED")
    if status != 200 or health.get("ok") is not True:
        raise GameMailTestError("WORKER_MAIL_HEALTH_FAILED_HTTP_" + str(status))
    sender_name = str(health.get("sender_name") or "")
    sender_id = health.get("sender_id")
    if sender_name != EXPECTED_SENDER or not isinstance(sender_id, int) or sender_id <= 0:
        raise GameMailTestError("UNEXPECTED_EVE_MAIL_SENDER")
    if health_only:
        return {"status": "EVE_GAME_MAIL_SENDER_HEALTHY",
                "sender_name": sender_name, "sender_id": sender_id,
                "sent": False}

    recipient_id = _resolve_recipient(recipient, client)
    stamp = now or datetime.now(timezone.utc)
    time_text = stamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subject = "EVE V4 游戏内邮件通道测试 " + time_text
    body = (
        "这是一封 V4 手动触发的 EVE 游戏内邮件测试。\\n"
        "发送角色：" + sender_name + "\\n"
        "接收角色：" + recipient + "\\n"
        "时间：" + time_text + "\\n"
        "本邮件不包含合同机会或真实利润，且不代表正式 V4 自动提醒已开启。"
    )
    unique_key = "v4-one-shot-test:" + str(idempotency or uuid.uuid4().hex)
    payload = {"recipient_id": recipient_id, "subject": subject,
               "body": body, "idempotency_key": unique_key}
    post_status, response = _request_json(
        client, "POST", WORKER_URL + "/api/send-mail",
        headers={**auth, "Content-Type": "application/json"},
        json=payload, timeout=65)
    if post_status == 401:
        raise GameMailTestError("WORKER_API_KEY_MISMATCH")
    if post_status == 409 or response.get("error") == "mail_sender_not_authorized":
        raise GameMailTestError("MAIL_SENDER_REAUTHORIZE_REQUIRED")
    if post_status != 200 or response.get("ok") is not True:
        raise GameMailTestError("EVE_GAME_MAIL_SEND_FAILED_HTTP_" + str(post_status))
    if response.get("skipped"):
        return {"status": "EVE_GAME_MAIL_ALREADY_SENT", "sent": False,
                "reason": "worker_idempotency_skip", "recipient": recipient,
                "recipient_id": recipient_id}
    try:
        mail_id = int(response.get("mail_id"))
        if mail_id <= 0:
            raise ValueError("nonpositive")
    except (TypeError, ValueError, OverflowError):
        raise GameMailTestError("EVE_GAME_MAIL_ACCEPTANCE_ID_MISSING") from None
    return {"status": "EVE_GAME_MAIL_TEST_SENT", "sent": True,
            "sender_name": sender_name, "sender_id": sender_id,
            "recipient": recipient, "recipient_id": recipient_id,
            "mail_id": mail_id, "subject": subject,
            "formal_opportunities_enabled": False,
            "local_scanner_modified": False}


def main():
    parser = argparse.ArgumentParser(
        description="Manually send one EVE Online in-game test mail via existing worker")
    parser.add_argument("--recipient", choices=RECIPIENTS, default="MikeChong")
    parser.add_argument("--health-only", action="store_true",
                        help="Check existing mail sender authorization without sending")
    args = parser.parse_args()
    try:
        result = run_test(args.recipient, health_only=args.health_only)
    except GameMailTestError as exc:
        # Only pre-approved error codes, no HTTP body or token in stdout.
        result = {"status": "EVE_GAME_MAIL_TEST_FAILED",
                  "sent": False, "reason": str(exc),
                  "secret_printed": False}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(4) from None
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
