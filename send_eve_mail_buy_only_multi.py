from __future__ import annotations

import os
import time

import requests

import buy_only_mail_templates as templates
import send_eve_mail_quality as quality
import send_eve_mail_quality_multi as multi
from send_eve_mail_fast import resolve_character

POLICY_VERSION = "buyonly-v1"


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
            "说明：剩余买单深度不足的物品按0估值；合同价>50亿、SKIN/SKINR价值占比≥50%的合同已剔除。完全相同的TOP列表不会重复发邮件。",
        )
    elif channel_key == "bpc-value":
        subject = subject.replace("BPC捡漏", "BPC捡漏·买单制造/蓝图价差")
        body = body.replace(
            "排序：制造利润按100%计；蓝图自身价值差按可比样本数折算可信度后参与排名（3/5/10/20+样本约为50%/65%/80%/90%）。",
            "制造利润仅按成品打Jita买单计算；蓝图同类挂牌价差是独立低估信号，不当作可兑现利润。合同价>50亿及SKIN/SKINR相关蓝图已剔除。",
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
    original_spot_builder = multi.install_spot_cosmetic_filter()

    def versioned_signature(picked):
        return POLICY_VERSION + "|" + original_top_signature(picked)

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
                # Explicit upstream 5xx responses are safe to retry. Unknown connection-loss
                # outcomes are not retried automatically because EVE may already have accepted mail.
                if status < 500 or attempt >= 3:
                    raise
                delay = 2 * attempt
                print(f"mail upstream HTTP {status}; retry {recipient_name} in {delay}s")
                time.sleep(delay)

    shared_history = quality.load_history()
    failures = []

    def run_channel(channel_name, sender):
        nonlocal shared_history
        history_before = shared_history.copy()
        history_after_counted_send = None
        push_count_recorded = False

        for name, recipient_id in recipients:
            quality.TOP_STATE = multi.recipient_top_state_path(name)
            top_state = quality.load_top_state()
            sent_successfully = False

            def send_one(_recipient_id, subject, body, channel_key, *, _name=name, _rid=recipient_id):
                nonlocal sent_successfully
                result = low_level_send_with_retry(_rid, subject, body, channel_key, _name)
                sent_successfully = True
                return result

            quality.base.send_mail = send_one
            # Exactly one successful recipient increments the shared opportunity push count.
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
                # Keep that recipient's TOP state unchanged so the next scan retries the digest.

        if history_after_counted_send is not None:
            shared_history = history_after_counted_send

    try:
        quality.base.deal_html = templates.deal_html
        quality.base.bpc_html = templates.bpc_html
        quality.top_signature = versioned_signature

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


if __name__ == "__main__":
    main()
