from __future__ import annotations

import math
import os
from dataclasses import dataclass

from .models import ExecutionProof, PolicyDecision


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
        return value if math.isfinite(value) else default
    except Exception:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class PolicyConfig:
    safe_min_profit: float = 30_000_000.0
    safe_min_roi: float = 0.10
    mail_min_profit: float = 50_000_000.0
    mail_min_roi: float = 0.10
    min_profit_per_m3: float = 2_000.0
    safe_change_pct: float = 0.15
    full_cash_mail_enabled: bool = False

    @classmethod
    def from_env(cls) -> "PolicyConfig":
        return cls(
            safe_min_profit=_env_float("V3_SAFE_MIN_PROFIT", 30_000_000.0),
            safe_min_roi=_env_float("V3_SAFE_MIN_ROI", 0.10),
            mail_min_profit=_env_float("MAIL_MIN_VERIFIED_NET_PROFIT", 50_000_000.0),
            mail_min_roi=_env_float("V3_MAIL_MIN_ROI", 0.10),
            min_profit_per_m3=_env_float("MIN_PROFIT_PER_M3", 2_000.0),
            safe_change_pct=_env_float("V3_SAFE_CHANGE_PCT", 0.15),
            full_cash_mail_enabled=_env_bool("V3_FULL_CASH_MAIL_ENABLED", False),
        )


def _finite(value: float, default: float = 0.0) -> float:
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except Exception:
        return default


def is_full_cash_exit(*, coverage: float, filled_units: int, requested_units: int) -> bool:
    """True only when the current live buy book can execute the entire bundle."""
    try:
        coverage = float(coverage)
        filled_units = int(filled_units)
        requested_units = int(requested_units)
    except Exception:
        return False
    return requested_units > 0 and filled_units >= requested_units and coverage >= 0.999999


def evaluate_execution(proof: ExecutionProof, cfg: PolicyConfig) -> PolicyDecision:
    """Apply strict policy to an immediate/cash-backed execution proof."""
    channel = proof.channel.upper()
    confidence = {
        "FULL_CASH": "CASH-SAFE",
        "PARTIAL_CASH_FLOOR": "CASH-FLOOR-SAFE",
        "BARTER": "BARTER-SAFE",
        "ARBITRAGE": "ARBITRAGE-SAFE",
        "CONVERSION": "CONVERSION-SAFE",
    }.get(channel, "EXECUTION-SUPPORTED")

    if proof.fatal or not proof.access_verified:
        return PolicyDecision("DANGER", confidence, False, "FATAL_OR_ACCESS_UNVERIFIED")
    if proof.destination_value <= 0 or proof.coverage <= 0:
        return PolicyDecision("RESEARCH", confidence, False, "NO_EXECUTABLE_EXIT")
    if proof.net_profit <= 0 or proof.net_roi <= 0:
        return PolicyDecision("RESEARCH", confidence, False, "NON_POSITIVE_ECONOMICS")
    if proof.stress_net_profit <= 0:
        return PolicyDecision("WATCH", confidence, False, "STRESS_NEGATIVE")
    if abs(_finite(proof.market_change_pct)) > cfg.safe_change_pct:
        return PolicyDecision("WATCH", confidence, False, "MARKET_CHANGED")
    if proof.profit_per_m3 < cfg.min_profit_per_m3:
        return PolicyDecision("WATCH", confidence, False, "LOW_PROFIT_DENSITY")
    if proof.net_profit < cfg.safe_min_profit:
        return PolicyDecision("WATCH", confidence, False, "BELOW_SAFE_PROFIT")
    if proof.net_roi < cfg.safe_min_roi:
        return PolicyDecision("WATCH", confidence, False, "BELOW_SAFE_ROI")

    mail_ok = (
        proof.net_profit >= cfg.mail_min_profit
        and proof.net_roi >= cfg.mail_min_roi
        and proof.profit_per_m3 >= cfg.min_profit_per_m3
    )
    if channel == "FULL_CASH" and not cfg.full_cash_mail_enabled:
        mail_ok = False
    if mail_ok:
        return PolicyDecision("MAIL", confidence, True, "FORMAL_GATE_PASSED")
    return PolicyDecision("SAFE", confidence, False, "SAFE_BELOW_MAIL_GATE")


def evaluate_listing(
    proof: ExecutionProof,
    cfg: PolicyConfig,
    *,
    max_fill_days: float,
    estimated_fill_days: float,
) -> PolicyDecision:
    """Listing value can support WATCH, but never masquerades as locked cash."""
    if proof.fatal or not proof.access_verified:
        return PolicyDecision("DANGER", "LIST-SUPPORTED", False, "FATAL_OR_ACCESS_UNVERIFIED")
    if proof.net_profit <= 0 or proof.net_roi <= 0:
        return PolicyDecision("RESEARCH", "LIST-SUPPORTED", False, "NON_POSITIVE_ECONOMICS")
    if estimated_fill_days <= 0 or estimated_fill_days > max_fill_days:
        return PolicyDecision("RESEARCH", "LIST-SUPPORTED", False, "FILL_TIME_UNSUPPORTED")
    if proof.stress_net_profit <= 0:
        return PolicyDecision("RESEARCH", "LIST-SUPPORTED", False, "STRESS_NEGATIVE")
    if proof.profit_per_m3 < cfg.min_profit_per_m3:
        return PolicyDecision("RESEARCH", "LIST-SUPPORTED", False, "LOW_PROFIT_DENSITY")
    return PolicyDecision("WATCH", "LIST-SUPPORTED", False, "LISTING_VALUE_SUPPORTED")
