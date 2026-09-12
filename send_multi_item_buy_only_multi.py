from __future__ import annotations

import send_multi_item_mail as base_multi
import send_multi_item_mail_multi as multi_sender
import buy_only_mail_templates as templates


def main():
    original_item_html = base_multi.item_html
    original_send = base_multi.base.send_mail

    def transformed_send(recipient_id, subject, body, channel_key):
        subject = subject.replace("多件合同捡漏", "多件合同捡漏·Jita买单")
        body = body.replace(
            "A=当前Jita买单深度下可立即兑现；B=流动性折扣后的正常市场价值。统一要求地点可达、估值覆盖≥90%、折价≥30%、价值差≥30M。",
            "仅按Jita 4-4真实买单深度估值；未被买单覆盖的剩余数量按0处理。不参考卖价。净利润≥30M、ROI≥10%。",
        )
        body = body.replace(
            "排序只看绝对净价值差；如果TOP10合同及顺序完全不变，本频道不会重复发邮件。",
            "排序只看Jita买单即时兑现净利润；合同价>50亿、SKIN/SKINR价值占比≥50%和不可执行地点已剔除。",
        )
        return original_send(recipient_id, subject, body, channel_key)

    try:
        base_multi.item_html = templates.multi_item_html
        base_multi.base.send_mail = transformed_send
        multi_sender.main()
    finally:
        base_multi.item_html = original_item_html
        base_multi.base.send_mail = original_send


if __name__ == "__main__":
    main()
