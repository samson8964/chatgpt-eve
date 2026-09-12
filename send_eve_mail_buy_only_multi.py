from __future__ import annotations

import send_eve_mail_quality as quality
import send_eve_mail_quality_multi as multi
import buy_only_mail_templates as templates


def main():
    # Replace only presentation; candidate selection/history/retry behavior stays in the proven
    # multi-recipient sender. The underlying result CSVs have already been rebuilt under the
    # Jita-buy-only policy before this step runs.
    original_deal_html = quality.base.deal_html
    original_bpc_html = quality.base.bpc_html
    original_send = quality.base.send_mail

    def transformed_send(recipient_id, subject, body, channel_key):
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
        return original_send(recipient_id, subject, body, channel_key)

    try:
        quality.base.deal_html = templates.deal_html
        quality.base.bpc_html = templates.bpc_html
        quality.base.send_mail = transformed_send
        multi.main()
    finally:
        quality.base.deal_html = original_deal_html
        quality.base.bpc_html = original_bpc_html
        quality.base.send_mail = original_send


if __name__ == "__main__":
    main()
