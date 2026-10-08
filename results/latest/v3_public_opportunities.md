# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T23:01:42.554Z
- Market snapshot: 2026-10-08T22:48:28.931Z
- Candidate universe: 24395; deep validation pool: 244; feasible: 182
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
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

- raw_contracts: `50112`
- eligible_contracts: `43458`
- market_executable_contracts: `24395`
- snapshot_candidates: `24395`
- candidate_pool: `607`
- location_executable: `244`
- feasible: `182`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `157`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18840`
- MARKET_INELIGIBLE_SINGLETON: `6056`
- UNSAFE_OR_UNVERIFIED_LOCATION: `363`
- HIGHSEC_RESTRICTED_CAPITAL: `58`
- FATAL_OR_ACCESS_UNVERIFIED: `12`
- SKIN_DOMINANT: `4`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
