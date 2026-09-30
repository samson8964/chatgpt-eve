from __future__ import annotations

import math
import os

DEFAULT_MIN_VERIFIED_NET_PROFIT = 100_000_000.0


def _configured_floor() -> float:
    raw = os.getenv("MAIL_MIN_VERIFIED_NET_PROFIT", str(int(DEFAULT_MIN_VERIFIED_NET_PROFIT)))
    try:
        value = float(raw)
    except Exception:
        return DEFAULT_MIN_VERIFIED_NET_PROFIT
    if not math.isfinite(value) or value < DEFAULT_MIN_VERIFIED_NET_PROFIT:
        return DEFAULT_MIN_VERIFIED_NET_PROFIT
    return value


MAIL_MIN_VERIFIED_NET_PROFIT = _configured_floor()


def finite_profit(value, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    return parsed if math.isfinite(parsed) else default


def meets_mail_profit_floor(value) -> bool:
    return finite_profit(value) >= MAIL_MIN_VERIFIED_NET_PROFIT
