# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T06:01:38.365Z
- Market snapshot: 2026-10-10T06:18:29.795Z
- Candidate universe: 24749; deep validation pool: 267; feasible: 197
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 157
- FORMAL MAIL: 3

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50453`
- eligible_contracts: `43839`
- market_executable_contracts: `24749`
- snapshot_candidates: `24749`
- candidate_pool: `610`
- location_executable: `267`
- feasible: `197`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `157`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18872`
- MARKET_INELIGIBLE_SINGLETON: `6294`
- UNSAFE_OR_UNVERIFIED_LOCATION: `343`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- FATAL_OR_ACCESS_UNVERIFIED: `14`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `2`
- LIST_DATA_INCOMPLETE: `1`
