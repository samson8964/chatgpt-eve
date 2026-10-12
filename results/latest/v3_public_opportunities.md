# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T11:32:00.192Z
- Market snapshot: 2026-10-12T11:19:14.707Z
- Candidate universe: 25081; deep validation pool: 270; feasible: 201
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 160
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

- raw_contracts: `50820`
- eligible_contracts: `44347`
- market_executable_contracts: `25081`
- snapshot_candidates: `25081`
- candidate_pool: `611`
- location_executable: `270`
- feasible: `201`
- full_cash: `2`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `8`
- research_watch: `160`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `19036`
- MARKET_INELIGIBLE_SINGLETON: `6509`
- UNSAFE_OR_UNVERIFIED_LOCATION: `341`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- FATAL_OR_ACCESS_UNVERIFIED: `14`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
