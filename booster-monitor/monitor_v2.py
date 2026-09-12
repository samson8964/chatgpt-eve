"""Cloud-first booster blueprint opportunity delivery with repeat counts and per-run spread alerts."""
from __future__ import annotations

from collections import defaultdict
import html
import statistics
import time

from app import Monitor
from core import ApiError, UncertainSend, stamp

CHANNEL_MANUFACTURING = "booster-manufacturing"
CHANNEL_SPREAD = "booster-spread"
MAIL_COOLDOWN = 1800

# Spread opportunity defaults. A candidate must be the cheapest verified contract
# for the same blueprint type and materially cheaper than the next-cheapest listing.
SPREAD_MIN_COMPARATORS = 2
SPREAD_MIN_DISCOUNT = 0.20
SPREAD_MIN_TOTAL_GAP = 30_000_000


def _isk(value: float) -> str:
    value = float(value or 0)
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:.0f}"


def build_spread_opportunities(rows):
    """Find same-blueprint BPCs with an actionable per-run price gap.

    Reference is the next-cheapest *other* verified contract. The median of other
    contracts is reported for context but does not determine eligibility.
    """
    groups = defaultdict(list)
    for row in rows:
        try:
            bp = int(row["bp"])
            runs = int(row["runs"])
            price = float(row["price"])
        except (KeyError, TypeError, ValueError):
            continue
        if runs <= 0 or price < 0:
            continue
        r = dict(row)
        r["per_run_price"] = price / runs
        groups[bp].append(r)

    out = []
    for bp, group in groups.items():
        if len(group) < SPREAD_MIN_COMPARATORS + 1:
            continue
        ordered = sorted(group, key=lambda r: (r["per_run_price"], r["price"], r["contract_id"]))
        candidate = ordered[0]
        others = ordered[1:]
        next_price = float(others[0]["per_run_price"])
        current_price = float(candidate["per_run_price"])
        if next_price <= 0 or current_price >= next_price:
            continue
        gap_per_run = next_price - current_price
        discount = gap_per_run / next_price
        total_gap = gap_per_run * int(candidate["runs"])
        if discount < SPREAD_MIN_DISCOUNT or total_gap < SPREAD_MIN_TOTAL_GAP:
            continue
        candidate = dict(candidate)
        candidate.update(
            comparator_count=len(others),
            next_per_run=next_price,
            median_other_per_run=float(statistics.median(r["per_run_price"] for r in others)),
            gap_per_run=gap_per_run,
            spread_discount=discount,
            spread_total_gap=total_gap,
        )
        out.append(candidate)

    out.sort(key=lambda r: (r["spread_total_gap"], r["spread_discount"]), reverse=True)
    return out


def manufacturing_digest(rows):
    lines = [
        "超强增效剂蓝图制造机会提醒",
        "以下为公开合同报价及制造估算，未购买。",
        "同一机会可重复提醒；每条均显示截至本次的累计推送次数。",
        "",
    ]
    for r in rows:
        lines.extend([
            f"{r['name']}：{r['copies']} 张，共 {r['runs']} 流程",
            f"已推送次数：第 {r['push_count']} 次",
            f"合同总价 {_isk(r['price'])}；每流程 {_isk(r['price']/r['runs'])}",
            f"预计总利润 {_isk(r['profit'])}；每 50 流程 {_isk(r['profit50'])}；回报率 {r['roi']:.0%}",
            f"成品七天成交 {r['week_volume']} 个（截至 {r['history_end']}）",
            f"星域编号 {r.get('region_id', '未知')}；交货地点编号 {r['location_id']}；合同编号 {r['contract_id']}",
            f"详情：https://www.adam4eve.eu/contract.php?id={r['contract_id']}",
            "",
        ])
    body = "<br>".join(html.escape(str(s)) for s in lines)
    body += "<br>" + "<br>".join(
        f'<url=contract:0//{int(r["contract_id"])}>在游戏中打开合同 {int(r["contract_id"])}</url>'
        for r in rows
    )
    return f"超强增效剂制造机会：{len(rows)} 个", body


def spread_digest(rows):
    lines = [
        "超强增效剂蓝图价差捡漏提醒",
        "这个通道只比较同种蓝图拷贝的每流程合同报价，不把制造利润作为入选条件。",
        "主要基准是同种蓝图中‘下一份最便宜合同’的每流程价格；其他合同中位价只作辅助参考。",
        f"默认门槛：至少 {SPREAD_MIN_COMPARATORS} 个其他可比合同、便宜 ≥ {SPREAD_MIN_DISCOUNT:.0%}、按本合同流程折算总价差 ≥ {_isk(SPREAD_MIN_TOTAL_GAP)}。",
        "",
    ]
    for r in rows:
        lines.extend([
            f"{r['name']}：{r['copies']} 张，共 {r['runs']} 流程",
            f"已推送次数：第 {r['push_count']} 次",
            f"本合同总价 {_isk(r['price'])}；每流程 {_isk(r['per_run_price'])}",
            f"下一份最便宜同种合同：每流程 {_isk(r['next_per_run'])}",
            f"其他同种合同中位价：每流程 {_isk(r['median_other_per_run'])}（可比 {r['comparator_count']} 份）",
            f"每流程价差 {_isk(r['gap_per_run'])}；低于下一档 {r['spread_discount']:.1%}",
            f"按本合同 {r['runs']} 流程折算的理论价差 {_isk(r['spread_total_gap'])}",
            f"星域编号 {r.get('region_id', '未知')}；交货地点编号 {r['location_id']}；合同编号 {r['contract_id']}",
            f"详情：https://www.adam4eve.eu/contract.php?id={r['contract_id']}",
            "",
        ])
    body = "<br>".join(html.escape(str(s)) for s in lines)
    body += "<br>" + "<br>".join(
        f'<url=contract:0//{int(r["contract_id"])}>在游戏中打开合同 {int(r["contract_id"])}</url>'
        for r in rows
    )
    return f"超强增效剂蓝图价差：{len(rows)} 个", body


class OpportunityMonitor(Monitor):
    """Monitor that keeps independent repeat counters for manufacturing/spread channels."""

    def _push_state(self):
        state = self.store.get("push_state", {})
        return state if isinstance(state, dict) else {}

    @staticmethod
    def _state_key(channel, recipient_id, contract_id):
        return f"{channel}:{int(recipient_id)}:{int(contract_id)}"

    def _live_verified_rows(self):
        rows = []
        for rec in self.store.rows("SELECT payload FROM alerts"):
            try:
                row = __import__("json").loads(rec["payload"])
                if (
                    int(row["contract_id"]) in self.active_ids
                    and int(row["contract_id"]) in self.verified_ids
                    and stamp(row["expired"]) > time.time()
                ):
                    rows.append(row)
            except (KeyError, TypeError, ValueError):
                continue
        return rows

    def _send_channel(self, channel, rows, digest_builder, sort_key):
        if not rows:
            return
        throttle_key = f"next_mail_at_{channel}"
        if time.time() < self.store.get(throttle_key, 0):
            return

        try:
            self.auth.access()
            rid = self.auth.recipient()["id"]
        except (ValueError, ApiError, RuntimeError) as e:
            self.state["mail_error"] = str(e)
            return

        state = self._push_state()
        picked = []
        for raw in sorted(rows, key=sort_key, reverse=True):
            key = self._state_key(channel, rid, raw["contract_id"])
            entry = state.get(key, {})
            # Unknown/sending may already have been delivered. Fail closed.
            if entry.get("state") in ("sending", "unknown"):
                continue
            row = dict(raw)
            row["push_count"] = int(entry.get("count", 0)) + 1
            picked.append(row)
            if len(picked) >= 10:
                break
        if not picked:
            return

        now = time.time()
        for row in picked:
            key = self._state_key(channel, rid, row["contract_id"])
            entry = dict(state.get(key, {}))
            entry.update(state="sending", updated=now)
            state[key] = entry
        self.store.put("push_state", state)
        if self.delivery_checkpoint:
            self.delivery_checkpoint()

        try:
            mid = self.auth.send(*digest_builder(picked))
            status, detail = "sent", f"游戏邮件编号 {mid}"
            self.store.put(throttle_key, time.time() + MAIL_COOLDOWN)
        except UncertainSend as e:
            status, detail = "unknown", str(e)
        except ApiError as e:
            status, detail = ("pending" if e.status in (420, 429) else "error"), str(e)
            self.store.put(throttle_key, time.time() + max(60, e.retry))
        except Exception:
            status, detail = "unknown", "投递结果未确认，请在游戏中核对"

        now = time.time()
        state = self._push_state()
        for row in picked:
            key = self._state_key(channel, rid, row["contract_id"])
            entry = dict(state.get(key, {}))
            if status == "sent":
                entry["count"] = int(entry.get("count", 0)) + 1
            entry.update(state=status, detail=detail, updated=now)
            state[key] = entry
        self.store.put("push_state", state)
        if status != "sent":
            self.state["mail_error"] = detail
        if self.delivery_checkpoint:
            self.delivery_checkpoint()

    def send_opportunities(self, current):
        with self.mail_lock:
            if self.store.get("paused", False) or not self.store.config()["mail_enabled"]:
                return
            self.state["mail_error"] = None

            # Manufacturing and blueprint-price spread are independent channels.
            self._send_channel(
                CHANNEL_MANUFACTURING,
                current,
                manufacturing_digest,
                lambda r: (r.get("profit50", 0), r.get("profit", 0)),
            )

            spread_rows = build_spread_opportunities(self._live_verified_rows())
            self.state["spread_opportunities"] = len(spread_rows)
            self._send_channel(
                CHANNEL_SPREAD,
                spread_rows,
                spread_digest,
                lambda r: (r.get("spread_total_gap", 0), r.get("spread_discount", 0)),
            )
