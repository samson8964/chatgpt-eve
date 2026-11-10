"""ESI-backed manufacturing *reference* installation fee for a named NPC facility.

The official public APIs give the solar-system manufacturing cost index and
market-adjusted material prices. They DO NOT quote an actual player job,
character skills, permissions, structure tax/rigs or guaranteed installation.

Default reference facility is Jita IV-4 Caldari Navy Assembly Plant (factory),
station 60003760, solar system 30000142. Facility tax 0.25%, SCC 4%,
Omega/no Alpha tax and no structure job-cost discount are explicit assumptions.
Do not silently reuse this NPC quote for a user-owned Upwell structure.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Callable, Mapping

ESI_BASE = "https://esi.evetech.net/latest"
JITA_SOLAR_SYSTEM_ID = 30000142
JITA_NPC_STATION_ID = 60003760
NPC_FACILITY_TAX_RATE = 0.0025
MANUFACTURING_SCC_RATE = 0.04
ALPHA_CLONE_TAX_RATE = 0.0025
UA = "chatgpt-eve V4 manufacturing reference (github.com/samson8964/chatgpt-eve)"
FEE_BASIS = "ESI_ADJUSTED_PRICES_SYSTEM_COST_INDEX_JITA_NPC_REFERENCE_NOT_JOB_QUOTE"


def _positive(value):
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


@dataclass(frozen=True)
class ManufacturingFeeContext:
    system_id: int
    facility_id: int
    manufacturing_cost_index: float
    adjusted_prices: Mapping[int, float]
    observed_at_utc: str
    facility_tax_rate: float = NPC_FACILITY_TAX_RATE
    scc_rate: float = MANUFACTURING_SCC_RATE
    alpha_tax_rate: float = 0.0
    system_index_multiplier: float = 1.0
    facility_name: str = "Jita IV-4 Caldari Navy Assembly Plant (NPC reference)"

    def __post_init__(self):
        for rate in (self.manufacturing_cost_index, self.facility_tax_rate,
                     self.scc_rate, self.alpha_tax_rate):
            if not math.isfinite(rate) or rate < 0 or rate > 1:
                raise ValueError("INVALID_MANUFACTURING_FEE_RATE")
        if not 0 < self.system_index_multiplier <= 1:
            raise ValueError("INVALID_MANUFACTURING_FACILITY_MULTIPLIER")
        if self.system_id <= 0 or self.facility_id <= 0:
            raise ValueError("INVALID_MANUFACTURING_FACILITY")

    def quote(self, recipe: Mapping, runs: int):
        """Return a reference job fee; None when *any* EIV input is missing.

        EIV is from unmodified SDE base material units (ME is not applied).
        Current BPC ME only changes the separate material-purchase cost.
        """
        if not isinstance(runs, int) or runs <= 0:
            return None
        materials = recipe.get("materials") if isinstance(recipe, Mapping) else None
        if not isinstance(materials, Mapping) or not materials:
            return None
        eiv = 0.0
        for raw_type, raw_qty in materials.items():
            try:
                type_id = int(raw_type)
                count = int(raw_qty)
            except (TypeError, ValueError, OverflowError):
                return None
            if type_id <= 0 or count <= 0:
                return None
            price = _positive(self.adjusted_prices.get(type_id))
            if price is None:
                return None
            eiv += price * count * runs
        if not math.isfinite(eiv) or eiv <= 0:
            return None
        # Individual components are rounded down to full ISK as in the UI.
        index_fee = math.floor(eiv * self.manufacturing_cost_index *
                               self.system_index_multiplier)
        facility_fee = math.floor(eiv * self.facility_tax_rate)
        scc_fee = math.floor(eiv * self.scc_rate)
        alpha_fee = math.floor(eiv * self.alpha_tax_rate)
        return {
            "manufacturing_fee_isk": index_fee + facility_fee + scc_fee + alpha_fee,
            "manufacturing_eiv_isk": eiv,
            "manufacturing_fee_index_isk": index_fee,
            "manufacturing_fee_facility_tax_isk": facility_fee,
            "manufacturing_fee_scc_isk": scc_fee,
            "manufacturing_fee_alpha_tax_isk": alpha_fee,
            "manufacturing_system_id": self.system_id,
            "manufacturing_facility_id": self.facility_id,
            "manufacturing_facility_name": self.facility_name,
            "manufacturing_cost_index": self.manufacturing_cost_index,
            "manufacturing_facility_tax_rate": self.facility_tax_rate,
            "manufacturing_scc_rate": self.scc_rate,
            "manufacturing_fee_observed_at_utc": self.observed_at_utc,
            "facility_fee_status": FEE_BASIS,
            "manufacturing_fee_snapshot_verified": True,
            "manufacturing_job_quote_verified": False,
        }


def load_jita_npc_fee_context(fetch: Callable | None = None):
    """Fetch exactly TWO public ESI snapshots once per whole scanner run.

    fetch(url) can be injected as the scanner's existing request() function;
    it may return either a payload or (payload, headers).
    Raises on HTTP/shape/missing-Jita failures; callers must fail closed.
    """
    if fetch is None:
        import requests

        def fetch(url):
            response = requests.get(url, timeout=45, headers={"User-Agent": UA})
            response.raise_for_status()
            return response.json()

    def payload(path):
        result = fetch(ESI_BASE + path)
        if isinstance(result, tuple):
            result = result[0]
        if not isinstance(result, list):
            raise ValueError("MANUFACTURING_ESI_RESPONSE_INVALID")
        return result

    systems = payload("/industry/systems/")
    prices = payload("/markets/prices/")
    cost_index = None
    for row in systems:
        if not isinstance(row, dict) or row.get("solar_system_id") != JITA_SOLAR_SYSTEM_ID:
            continue
        for activity in row.get("cost_indices", []):
            if activity.get("activity") == "manufacturing":
                cost_index = activity.get("cost_index")
                break
    if cost_index is None:
        raise ValueError("JITA_MANUFACTURING_SYSTEM_INDEX_MISSING")
    adjusted = {}
    for row in prices:
        if not isinstance(row, dict):
            continue
        try:
            type_id = int(row["type_id"])
        except (ValueError, TypeError, KeyError, OverflowError):
            continue
        price = _positive(row.get("adjusted_price"))
        if price is not None:
            adjusted[type_id] = price
    if not adjusted:
        raise ValueError("MANUFACTURING_ADJUSTED_PRICES_MISSING")
    return ManufacturingFeeContext(
        system_id=JITA_SOLAR_SYSTEM_ID,
        facility_id=JITA_NPC_STATION_ID,
        manufacturing_cost_index=float(cost_index),
        adjusted_prices=adjusted,
        observed_at_utc=datetime.now(timezone.utc).isoformat(),
    )
