"""Throttled V4 storage pressure notification over EXISTING research Gmail.

Independent from opportunity mail and both EVE market channels. No new
credentials, no ESI, no calendar access, no filesystem cleanup.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path


def send_capacity_alert(root: Path, health: dict, *, now=None,
                        vault=None, smtp_factory=None) -> dict:
    root = Path(root)
    severity = health.get("severity")
    if severity not in ("WARNING", "STOP"):
        return {"status": "NO_CAPACITY_ALERT_NEEDED", "sent": False}
    from v4.research_mail import (
        SERVICE, _config, _windows_keyring, _send_review_smtp,
    )
    config = _config(root)
    if config is None:
        return {"status": "CAPACITY_GMAIL_NOT_CONFIGURED", "sent": False}
    now = now or datetime.now(timezone.utc)
    # One notification per severity per UTC day. STOP still escalates even
    # after an earlier WARNING. Never reuse opportunity-mail receipts.
    receipt = (root / "logs" / "storage-alert-receipts" /
               (now.strftime("%Y%m%d") + "-" + severity + ".json"))
    if receipt.is_symlink() or receipt.parent.is_symlink():
        return {"status": "CAPACITY_RECEIPT_PATH_UNSAFE", "sent": False}
    if receipt.exists():
        return {"status": "CAPACITY_ALERT_ALREADY_SENT_TODAY",
                "sent": False}
    vault = vault or _windows_keyring()
    password = vault.get_password(SERVICE, config["sender"])
    if not password:
        raise RuntimeError("CAPACITY_GMAIL_VAULT_SECRET_MISSING")
    message = EmailMessage()
    message["From"] = config["sender"]
    message["To"] = config["recipient"]
    message["Subject"] = ("【EVE V4 磁盘告警】" +
                          ("下一轮扫描将受阻" if severity == "STOP"
                           else "容量下降过快或剩余空间偏低"))
    free = health.get("free_gib")
    free_label = (f"{free:.2f} GiB" if isinstance(free, (int, float))
                  else "未知")
    trend = health.get("growth") or {}
    message.set_content(
        "V4 本地存储容量预警（非捡漏机会）。\n"
        f"级别：{severity}\n"
        f"当前可用容量：{free_label}\n"
        f"过去一段时间可用容量日变化："
        f"{trend.get('daily_free_gib_change')} GiB/天\n"
        "低于20 GiB时，Shadow后续运行会跳过新的采集。\n"
        "本提醒不会清除历史数据，也不会重启已禁用的市场机会任务。\n"
        "请在本机运行 python -m v4.storage_governor 核对容量分类。\n"
    )
    _send_review_smtp(message, config["sender"], password,
                      smtp_factory=smtp_factory)
    receipt.parent.mkdir(parents=True, exist_ok=True)
    temporary = receipt.with_suffix(".json.part")
    if temporary.exists() or temporary.is_symlink():
        return {"status": "CAPACITY_ALERT_SENT_RECEIPT_BLOCKED",
                "sent": True}
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump({"schema": 1, "severity": severity,
                       "sent_at": now.isoformat()}, stream)
        os.replace(temporary, receipt)
    finally:
        temporary.unlink(missing_ok=True)
    return {"status": "CAPACITY_ALERT_SENT", "sent": True,
            "severity": severity}
