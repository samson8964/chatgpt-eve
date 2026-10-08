# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T20:31:46.050Z
- Market snapshot: 2026-10-08T20:48:35.434Z
- Candidate universe: 24402; deep validation pool: 247; feasible: 192
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 161
- FORMAL MAIL: 2

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50160`
- eligible_contracts: `43466`
- market_executable_contracts: `24402`
- snapshot_candidates: `24402`
- candidate_pool: `607`
- location_executable: `247`
- feasible: `192`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `161`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18844`
- MARKET_INELIGIBLE_SINGLETON: `6097`
- UNSAFE_OR_UNVERIFIED_LOCATION: `360`
- HIGHSEC_RESTRICTED_CAPITAL: `50`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- BARTER_PROCUREMENT_INCOMPLETE: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- NO_EXECUTABLE_ITEMS: `2`
- LIST_DATA_INCOMPLETE: `2`
