from __future__ import annotations

import json
import os
import time

import requests

import buy_only_mail_templates as templates
import send_eve_mail_quality as quality
import send_eve_mail_quality_multi as multi
from send_eve_mail_fast import resolve_character

POLICY_VERSION = "buyonly-v2-exec-2"
RESEND_ABS_PROFIT = float(os.getenv("MAIL_RESEND_ABS_PROFIT", "20000000"))
RESEND_REL_PROFIT = float(os.getenv("MAIL_RESEND_REL_PROFIT", "0.10"))
RESEND_ROI_DELTA = float(os.getenv("MAIL_RESEND_ROI_DELTA", "0.02"))
REMIND_AFTER_HOURS = float(os.getenv("MAIL_REMIND_AFTER_HOURS", "6"))
BPC_MFG_MAIL_EXCLUDED_RECIPIENTS = {
    x.strip().casefold()
    for x in os.getenv("BPC_MFG_MAIL_EXCLUDED_RECIPIENTS", "").split(",")
    if x.strip()
}


def _text(v, default=""):
    if v is None:
        return default
    s = str(v).strip()
    if not s or s.lower() in {"nan", "none"}:
        return default
    return s


def _candidate_snapshot(channel: str, picked):
    out = []
    for c in picked:
        row = c["row"]
        metric = float(quality.candidate_metric(channel, row))
        if channel == "spot-deals":
            roi = quality.finite(row.get("mail_net_roi"), c.get("roi", 0.0))
        else:
            roi = quality.finite(row.get("net_roi"), c.get("roi", 0.0))
        status = _text(row.get("execution_status"), "SAFE").upper()
        grade = _text(row.get("score_grade"), _text(row.get("recommendation"), ""))
        out.append(
            {
                "id": int(c["contract_id"]),
                "metric": round(metric, 2),
                "roi": round(float(roi), 6),
                "status": status,
                "grade": grade,
            }
        )
    return out


def _signature(channel: str, picked):
    payload = _candidate_snapshot(channel, picked)
    return POLICY_VERSION + "|" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _old_snapshot(state, channel: str):
    if state.empty:
        return None, None
    mask = state["channel"].astype(str) == channel
    if not mask.any():
        return None, None
    row = state.loc[mask].iloc[-1]
    raw = str(row.get("signature", ""))
    updated_at = row.get("updated_at", "")
    prefix = POLICY_VERSION + "|"
    if not raw.startswith(prefix):
        return None, updated_at
    try:
        parsed = json.loads(raw[len(prefix) :])
        if not isinstance(parsed, list):
            return None, updated_at
        return parsed, updated_at
    except Exception:
        return None, updated_at


def _smart_top_is_unchanged(state, channel: str, picked):
    current = _candidate_snapshot(channel, picked)
    previous, updated_at = _old_snapshot(state, channel)

    if previous is None:
        print(f"{channel} reminder trigger: policy/state upgraded")
        return False

    current_ids = [int(x.get("id", 0)) for x in current]
    previous_ids = [int(x.get("id", 0)) for x in previous]
    # Ranking-only movement is noise. Membership changes remain actionable;
    # meaningful value/ROI/status/grade changes are evaluated below per contract.
    if len(current_ids) != len(previous_ids) or set(current_ids) != set(previous_ids):
        print(f"{channel} reminder trigger: TOP membership changed")
        return False

    # Do not periodically send empty digests. A change from non-empty to empty is
    # already caught above and will still produce one clear notification.
    if not current:
        return True

    previous_by_id = {int(x.get("id", 0)): x for x in previous}
    for cur in current:
        cid = int(cur["id"])
        old = previous_by_id.get(cid)
        if old is None:
            print(f"{channel} reminder trigger: new contract {cid}")
            return False

        cur_metric = float(cur.get("metric", 0.0) or 0.0)
        old_metric = float(old.get("metric", 0.0) or 0.0)
        delta = abs(cur_metric - old_metric)
        rel = delta / max(abs(old_metric), 1.0)
        if delta >= RESEND_ABS_PROFIT or rel >= RESEND_REL_PROFIT:
            print(
                f"{channel} reminder trigger: contract {cid} value changed "
                f"delta={delta:.0f} rel={rel:.1%}"
            )
            return False

        cur_roi = float(cur.get("roi", 0.0) or 0.0)
        old_roi = float(old.get("roi", 0.0) or 0.0)
        if abs(cur_roi - old_roi) >= RESEND_ROI_DELTA:
            print(
                f"{channel} reminder trigger: contract {cid} ROI changed "
                f"delta={abs(cur_roi-old_roi):.2%}"
            )
            return False

        if _text(cur.get("status"), "SAFE") != _text(old.get("status"), "SAFE"):
            print(f"{channel} reminder trigger: contract {cid} execution status changed")
            return False

        if _text(cur.get("grade")) != _text(old.get("grade")):
            print(f"{channel} reminder trigger: contract {cid} grade changed")
            return False

    try:
        ts = quality.pd.to_datetime(updated_at, utc=True, errors="coerce")
        if quality.pd.notna(ts):
            age_h = (quality.pd.Timestamp.now(tz="UTC") - ts).total_seconds() / 3600.0
            if age_h >= REMIND_AFTER_HOURS:
                print(f"{channel} reminder trigger: still SAFE after {age_h:.1f}h")
                return False
    except Exception:
        pass

    return True


def transform_content(subject: str, body: str, channel_key: str):
    if channel_key == "spot-deals":
        subject = subject.replace("现货捡漏", "现货捡漏·Jita买单")
        body = body.replace(
            "A类即时买单和B类挂单机会均可推送；统一要求净利润≥30M、ROI≥10%。",
            "仅推送Jita 4-4真实买单深度可兑现机会；净利润≥30M、ROI≥10%，不参考卖价。",
        )
        body = body.replace(
            "排序：只按当前价差空间（净利润ISK）从大到小；A即时买单、B挂单都参与。",
            "排序：按Jita买单即时兑现净利润从大到小；不使用卖价、挂单估值或卖单折价。",
        )
        body = body.replace(
            "说明：B类是挂单潜在利润，不是即时可兑现利润；风险标签继续保留，但不参与价差排名。完全相同的TOP列表不会重复发邮件。",
            "说明：剩余买单深度不足的物品按0估值；合同价>50亿、SKIN/SKINR价值占比≥50%的合同已剔除。相同合同在利润/ROI/等级明显变化或持续SAFE满6小时后会再次提醒。",
        )
    elif channel_key == "bpc-value":
        subject = subject.replace("BPC捡漏", "BPC制造捡漏·V2 SAFE")
        body = (
            "<b>Opportunity Engine V2：自动邮件仅包含 SAFE 制造套利；CHANGED/DANGER 与蓝图挂牌价低估信号不自动推荐。</b><br><br>"
            + body
        )
        body = body.replace(
            "排序：制造利润按100%计；蓝图自身价值差按可比样本数折算可信度后参与排名（3/5/10/20+样本约为50%/65%/80%/90%）。",
            "排序：仅按V2实时复核后的制造机会；材料与成品均按实时Jita订单深度、VWAP、滑点和压力测试计算。",
        )
        body = body.replace(
            "说明：蓝图挂牌可比价不是实际成交价，因此样本越少折扣越大；制造净利润是独立证据。完全相同的TOP列表不会重复发邮件。",
            "说明：自动邮件仅推送SAFE制造机会；同一合同净利润变化≥20M或≥10%、ROI变化≥2个百分点、等级变化，或持续SAFE满6小时会再次提醒。",
        )
    return subject, body


def main():
    if not quality.base.API_KEY:
        raise RuntimeError("Missing EVE_MAIL_API_KEY")

    names = multi.recipient_names()
    recipients = [(name, resolve_character(name)) for name in names]
    primary_name = os.getenv("EVE_MAIL_RECIPIENT_NAME", "").strip() or names[0]
    stamp = quality.pd.Timestamp.now(tz="Asia/Shanghai").strftime("%m-%d %H:%M")

    original_send = quality.base.send_mail
    original_record_history = quality.record_history
    original_top_state_path = quality.TOP_STATE
    original_deal_html = quality.base.deal_html
    original_bpc_html = quality.base.bpc_html
    original_top_signature = quality.top_signature
    original_top_is_unchanged = quality.top_is_unchanged
    original_spot_builder = multi.install_spot_cosmetic_filter()

    active_channel = ""

    def smart_signature(picked):
        return _signature(active_channel, picked)

    def low_level_send_with_retry(recipient_id, subject, body, channel_key, recipient_name):
        subject, body = transform_content(subject, body, channel_key)
        for attempt in range(1, 4):
            try:
                print(
                    f"sending {channel_key} to {recipient_name} ({recipient_id}) "
                    f"attempt={attempt}"
                )
                return original_send(recipient_id, subject, body, channel_key)
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else 0
                if status < 500 or attempt >= 3:
                    raise
                delay = 2 * attempt
                print(f"mail upstream HTTP {status}; retry {recipient_name} in {delay}s")
                time.sleep(delay)

    shared_history = quality.load_history()
    failures = []

    def run_channel(channel_name, sender):
        nonlocal shared_history, active_channel
        active_channel = channel_name
        history_before = shared_history.copy()
        history_after_counted_send = None
        push_count_recorded = False

        for name, recipient_id in recipients:
            if channel_name == "bpc-value" and name.casefold() in BPC_MFG_MAIL_EXCLUDED_RECIPIENTS:
                print(f"{channel_name} skipped for {name}: recipient opted out of BPC manufacturing mail")
                continue

            quality.TOP_STATE = multi.recipient_top_state_path(name)
            top_state = quality.load_top_state()
            sent_successfully = False

            def send_one(_recipient_id, subject, body, channel_key, *, _name=name, _rid=recipient_id):
                nonlocal sent_successfully
                result = low_level_send_with_retry(_rid, subject, body, channel_key, _name)
                sent_successfully = True
                return result

            quality.base.send_mail = send_one
            quality.record_history = (
                original_record_history
                if not push_count_recorded
                else (lambda hist, channel, picked: hist)
            )
            try:
                returned_history, _ = sender(
                    recipient_id,
                    stamp,
                    history_before.copy(),
                    top_state,
                )
                if sent_successfully and not push_count_recorded:
                    history_after_counted_send = returned_history
                    push_count_recorded = True
            except Exception as exc:
                failures.append((channel_name, name, exc))
                print(
                    f"::warning::{channel_name} mail failed for {name}: "
                    f"{type(exc).__name__}: {exc}"
                )

        if history_after_counted_send is not None:
            shared_history = history_after_counted_send

    try:
        quality.base.deal_html = templates.deal_html
        quality.base.bpc_html = templates.bpc_html
        quality.top_signature = smart_signature
        quality.top_is_unchanged = _smart_top_is_unchanged

        run_channel("spot-deals", quality.send_spot)
        run_channel("bpc-value", quality.send_bpc)

        quality.HISTORY.parent.mkdir(parents=True, exist_ok=True)
        shared_history.to_csv(quality.HISTORY, index=False)
    finally:
        quality.base.send_mail = original_send
        quality.record_history = original_record_history
        quality.TOP_STATE = original_top_state_path
        quality.base.deal_html = original_deal_html
        quality.base.bpc_html = original_bpc_html
        quality.top_signature = original_top_signature
        quality.top_is_unchanged = original_top_is_unchanged
        quality.build_spot_candidates = original_spot_builder

    if failures:
        primary_failures = [
            (channel, exc)
            for channel, name, exc in failures
            if name.casefold() == primary_name.casefold()
        ]
        print(
            f"::warning::mail delivery incomplete: failures={len(failures)} "
            f"primary_failures={len(primary_failures)}; scan results remain valid and will be saved."
        )
        for channel, name, exc in failures:
            print(f"mail failure detail: channel={channel} recipient={name} error={exc}")
        if primary_failures:
            failed_channels = ",".join(channel for channel, _ in primary_failures)
            raise RuntimeError(f"primary recipient mail delivery failed for channel(s): {failed_channels}")


if __name__ == "__main__":
    main()
