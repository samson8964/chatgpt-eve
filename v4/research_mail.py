"""Explicitly enabled V4 contract RESEARCH Gmail digest after local Windows scan.

No false executable-opportunity claims. Uses a separate Windows Credential
Manager secret and SMTP SSL. The scanner never imports this module by default,
and never sends under the formal opportunity-mail identity.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from v4.contract_review import make_review

SERVICE = "eve-v4-contract-review-gmail"
CONFIG = Path("config/research_gmail.json")
PROOF_DIR = Path("mail-review/receipts")
ADDRESS = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _windows_keyring():
    if sys.platform != "win32":
        raise RuntimeError("WINDOWS_CREDENTIAL_VAULT_REQUIRED")
    import keyring
    backend = keyring.get_keyring()
    if not type(backend).__module__.startswith("keyring.backends.Windows"):
        raise RuntimeError("WINDOWS_CREDENTIAL_VAULT_BACKEND_REQUIRED")
    return keyring


def _safe_address(value: str) -> str:
    value = str(value).strip()
    if len(value) > 160 or not ADDRESS.fullmatch(value) or "\n" in value or "\r" in value:
        raise ValueError("INVALID_GMAIL_ADDRESS")
    return value


def configure(root: Path, sender: str, recipient: str, app_password: str,
              *, vault=None) -> dict:
    sender, recipient = _safe_address(sender), _safe_address(recipient)
    if not sender.lower().endswith("@gmail.com"):
        raise ValueError("SENDER_MUST_BE_GMAIL")
    secret = "".join(str(app_password).split())
    if not 12 <= len(secret) <= 64 or not secret.isascii() or not secret.isalnum():
        raise ValueError("INVALID_GMAIL_APP_PASSWORD")
    root = Path(root)
    vault = vault or _windows_keyring()
    vault.set_password(SERVICE, sender, secret)
    path = root / CONFIG
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    try:
        tmp.write_text(json.dumps({
            "schema": 1, "enabled": True,
            "mode": "V4_CONTRACT_RESEARCH_ONLY",
            "sender": sender, "recipient": recipient,
        }, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return {"configured": True, "mode": "CONTRACT_RESEARCH_ONLY",
            "secret_stored_in_windows_vault": True, "secret_printed": False}


def _config(root: Path) -> dict | None:
    path = Path(root) / CONFIG
    if not path.is_file():
        return None
    config = json.loads(path.read_text("utf-8"))
    if isinstance(config, dict) and config.get("enabled") is False:
        return None
    if (not isinstance(config, dict) or config.get("schema") != 1
            or config.get("enabled") is not True
            or config.get("mode") != "V4_CONTRACT_RESEARCH_ONLY"):
        raise RuntimeError("REVIEW_GMAIL_CONFIG_INVALID")
    config["sender"] = _safe_address(config.get("sender", ""))
    config["recipient"] = _safe_address(config.get("recipient", ""))
    return config


def disable(root: Path) -> dict:
    path = Path(root) / CONFIG
    if path.is_file():
        config = json.loads(path.read_text("utf-8"))
        config["enabled"] = False
        tmp = path.with_suffix(".part")
        try:
            tmp.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
    return {"research_mail_enabled": False, "formal_opportunity_mail_enabled": False}


def _isk(value) -> str:
    if value is None:
        return "未提供"
    return f"{float(value):,.0f} ISK"


def render_review(review: dict) -> tuple[str,str]:
    """No LIVE VERIFIED wording is allowed; one digest per scan folder."""
    stamp = review.get("finished_at")
    try:
        dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        when = dt.astimezone().strftime("%m-%d %H:%M") if dt.tzinfo else "--:--"
    except (ValueError, TypeError):
        when = "--:--"
    good = (review.get("coverage_gate") ==
            "INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED" and
            review.get("source_input_integrity") == "ALL_PARSED")
    leads = review.get("research_leads") or []
    if not good:
        leads = []  # incomplete source must never mail apparent opportunities
    subject = (f"【EVE V4合同审核·非交易提醒】{when} | "
               f"{len(leads)}条快照待复核" if good else
               f"【EVE V4合同扫描异常·非交易提醒】{when}")
    lines = [
        "EVE V4 合同捡漏审核简报（非正式机会推送）",
        "扫描时间：" + when,
        "运行记录：" + str(review.get("run_folder")),
        "采集完整性：" + str(review.get("coverage_gate")),
        "真实本轮Jita现金合同审核：" + str(review.get("contract_proofs_audited")),
        "SQLite证明：" + str(review.get("sqlite_unique_proofs")),
        "本轮初步满足计算门槛的合同：" + str(review.get("research_leads_total")),
        "合同统一估价：Jita IV - Moon 4 - Caldari Navy Assembly Plant (60003760) 的买单深度快照。",
        "合同所在地仅决定提货位置、预估运输费及访问/运输风险。",
        "全部候选均未复核实时合同/买单，不能据此购买。",
        "",
    ]
    if not good:
        lines.extend(["本轮源完整性未通过；为防误导，隐藏全部合同候选。",""])
    elif not leads:
        lines.extend(["本轮没有符合当前审核口径且有可解释利润的合同候选。",""])
    else:
        for n, p in enumerate(leads, 1):
            item_names = list(p["included_items"].items())[:8]
            item_text = ", ".join(f"Type {k} ×{v}" for k,v in item_names)
            lines.extend([
                f"{n}. 合同ID：{p['contract_id']} （{p['review_tier']} / 未实时核实）",
                "合同价：" + _isk(p.get("contract_price")),
                "合同所在地：" + str(p.get("source_location") or "未知"),
                "兑现参考：Jita 4-4 买单（不是合同当地买盘）",
                "运输预估：" + _isk(p.get("haul_estimate_isk")),
                "投资额（含运输预估）：" + _isk(p.get("investment")),
                "快照估计净利（已扣运输预估）：" + _isk(p.get("net_profit_snapshot")),
                "快照ROI：" + f"{p.get('roi_snapshot',0)*100:.1f}%",
                "移除最佳买单后压力利润：" + _isk(p.get("stress_profit_snapshot")),
                "物品：" + item_text,
                "到期：" + (p.get("expires_at") or "未知"),
                "物流及可达性：尚未实地核验（估算不保证可达或可运输）",
                "EVE合同链接：https://eve-contract-opener.99617224.workers.dev/c/" + str(p["contract_id"]),
                "必须先查合同仍存活、全部物品和蓝图属性、实时买单深度、位置及运输可达性。",
                "",
            ])
    lines.append("主要未通过原因（不是已确认的捡漏）：")
    for reason, count in list((review.get("contract_rejection_reasons") or {}).items())[:8]:
        lines.append(f"- {reason}：{count}")
    lines.extend(["", "本邮件只提供研究证据，不代表立即可以兑现。正式执行性和邮件仍未验证。",
                  "本邮件由本地 V4 研究简报通道独立发送；不会恢复 V3，也不会自动交易。"])
    return subject, "\n".join(lines)


def send_transport_test(root: Path, *, vault=None, smtp_factory=None) -> dict:
    """Explicit, one-off SMTP proof independent of scan age or pricing.

    This message cannot be confused with a contract opportunity. No secrets
    leave the Windows vault except the SMTP authentication exchange with Gmail.
    It does not write scan receipts, change the mail schedule, or inspect ESI.
    """
    config = _config(Path(root))
    if config is None:
        return {"status": "REVIEW_GMAIL_DISABLED", "sent": False}
    vault = vault or _windows_keyring()
    password = vault.get_password(SERVICE, config["sender"])
    if not password:
        raise RuntimeError("REVIEW_GMAIL_VAULT_SECRET_MISSING")
    msg = EmailMessage()
    msg["From"] = config["sender"]
    msg["To"] = config["recipient"]
    msg["Subject"] = "EVE V4 Gmail SMTP 通道测试（非捡漏机会）"
    msg.set_content(
        "EVE V4 Gmail SMTP 测试邮件已成功提交给 Gmail 发信服务器。\\n"
        "这封邮件不包含合同、利润或自动扫描结果。\\n"
        "后续合同审核简报仍以新一轮 Jita 4-4 买盘估值扫描为准。\\n"
        "本邮件由本机 --test-smtp 显式发送，不代表正式机会提醒已启用。\\n"
    )
    smtp_factory = smtp_factory or smtplib.SMTP_SSL
    with smtp_factory("smtp.gmail.com", 465, timeout=35) as client:
        client.login(config["sender"], password)
        client.send_message(msg)
    return {"status": "REVIEW_GMAIL_TEST_SENT",
            "sent": True, "research_only": True, "formal_mail": False,
            "secret_printed": False}


def send_review(root: Path, *, expected_run: str | None = None,
                vault=None, smtp_factory=None) -> dict:
    root = Path(root)
    config = _config(root)
    if config is None:
        return {"status":"REVIEW_GMAIL_DISABLED", "sent":False}
    review = make_review(root)
    run_name = review["run_folder"]
    if expected_run is not None and run_name != expected_run:
        raise RuntimeError("LATEST_COMPLETED_RUN_NOT_CURRENT")
    receipt = root / PROOF_DIR / (run_name + ".json")
    if receipt.is_file():
        return {"status":"REVIEW_GMAIL_ALREADY_SENT", "sent":False,
                "run_folder_name":run_name}
    vault = vault or _windows_keyring()
    password = vault.get_password(SERVICE, config["sender"])
    if not password:
        raise RuntimeError("REVIEW_GMAIL_VAULT_SECRET_MISSING")
    subject, body = render_review(review)
    msg = EmailMessage()
    msg["From"] = config["sender"]
    msg["To"] = config["recipient"]
    msg["Subject"] = subject
    unique = hashlib.sha256((run_name + "|"+config["recipient"]).encode()).hexdigest()
    msg["Message-ID"] = "<eve-v4-review-"+unique[:32]+"@gmail.com>"
    msg.set_content(body)
    smtp_factory = smtp_factory or smtplib.SMTP_SSL
    with smtp_factory("smtp.gmail.com",465,timeout=35) as client:
        client.login(config["sender"], password)
        client.send_message(msg)
    # Receipt is written only after the SMTP server accepted the email.
    receipt.parent.mkdir(parents=True, exist_ok=True)
    tmp = receipt.with_suffix(".part")
    try:
        tmp.write_text(json.dumps({"schema":1,"run":run_name,"sent_at":
                       datetime.now(timezone.utc).isoformat(),
                       "research_only":True,"formal_mail":False}), encoding="utf-8")
        os.replace(tmp,receipt)
    finally:
        tmp.unlink(missing_ok=True)
    return {"status":"REVIEW_GMAIL_SENT","sent":True,
            "run_folder_name":run_name,
            "research_only":True,"formal_mail":False,
            "contract_leads_included": len(review.get("research_leads") or [])
                 if review.get("source_input_integrity")=="ALL_PARSED" and
                 review.get("coverage_gate")=="INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED" else 0}


def main():
    parser=argparse.ArgumentParser(description="Enable or send V4 research-only Gmail summary")
    opt=parser.add_mutually_exclusive_group(required=True)
    opt.add_argument("--configure",action="store_true")
    opt.add_argument("--gui",action="store_true",help="Show masked Windows Gmail password window")
    opt.add_argument("--send-now",action="store_true")
    opt.add_argument("--test-smtp",action="store_true",help="Send one non-opportunity Gmail SMTP test")
    opt.add_argument("--disable",action="store_true")
    parser.add_argument("--data-root",type=Path,
                        default=Path.home()/"EVE-V4-Data")
    args=parser.parse_args()
    if args.gui:
        from v4.research_mail_gui import launch_dialog
        saved = launch_dialog(args.data_root)
        result = {"gui_saved":saved, "secret_printed":False,
                  "formal_mail_enabled":False, "sent":False}
    elif args.configure:
        print("Configure Gmail application password for research-only V4 email.")
        user=input("Gmail sender address: ").strip()
        dest=input("Recipient (press Enter for sender): ").strip() or user
        password=getpass.getpass("Gmail App Password (hidden input): ")
        result=configure(args.data_root,user,dest,password)
    elif args.disable:
        result=disable(args.data_root)
    elif args.test_smtp:
        try:
            result=send_transport_test(args.data_root)
        except (OSError, RuntimeError, smtplib.SMTPException) as exc:
            # Never print SMTP server details, exception arguments or secrets.
            result={"status":"REVIEW_GMAIL_TEST_FAILED","sent":False,
                    "error_type":type(exc).__name__,"secret_printed":False}
            print(json.dumps(result,ensure_ascii=False,indent=2))
            raise SystemExit(4) from None
    else:
        result=send_review(args.data_root)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
