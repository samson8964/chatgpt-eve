from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionProof:
    """One auditable economic proof for one exit route.

    The proof intentionally separates market facts from policy. Engines calculate
    facts; PolicyEngine decides whether the proof is RESEARCH/WATCH/SAFE/MAIL.
    """

    opportunity_id: str
    channel: str
    source_cost: float
    destination_value: float
    sales_tax: float = 0.0
    broker_fee: float = 0.0
    haul_cost: float = 0.0
    other_cost: float = 0.0
    volume_m3: float = 0.0
    source_depth_complete: bool = True
    destination_depth_complete: bool = True
    access_verified: bool = True
    stress_value: float = 0.0
    live_timestamp: str = ""
    coverage: float = 0.0
    net_profit: float = 0.0
    net_roi: float = 0.0
    stress_net_profit: float = 0.0
    profit_per_m3: float = 0.0
    market_change_pct: float = 0.0
    fatal: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        details = row.pop("details", {}) or {}
        for key, value in details.items():
            row.setdefault(key, value)
        return row


@dataclass(frozen=True)
class PolicyDecision:
    stage: str
    confidence_class: str
    mail_eligible: bool
    reason: str

    @property
    def execution_status(self) -> str:
        if self.stage in {"MAIL", "SAFE"}:
            return "SAFE"
        if self.stage == "WATCH":
            return "WATCH"
        if self.stage == "DANGER":
            return "DANGER"
        return "RESEARCH"
