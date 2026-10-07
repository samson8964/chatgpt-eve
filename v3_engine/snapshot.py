from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MarketSnapshot:
    """Shared per-run market data. A type/side is acquired once and reused."""

    snapshot_buys: dict[int, list[dict]] = field(default_factory=dict)
    snapshot_sells: dict[int, list[dict]] = field(default_factory=dict)
    live_buys: dict[int, list[dict]] = field(default_factory=dict)
    live_sells: dict[int, list[dict]] = field(default_factory=dict)
    history: dict[int, dict] = field(default_factory=dict)
    failed_buy_types: set[int] = field(default_factory=set)
    failed_sell_types: set[int] = field(default_factory=set)
    failed_history_types: set[int] = field(default_factory=set)
    live_buy_at: str = ""
    live_sell_at: str = ""
