# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T07:01:47.013Z
- Market snapshot: 2026-10-12T06:49:40.967Z
- Candidate universe: 25058; deep validation pool: 249; feasible: 168
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 157
- FORMAL MAIL: 1

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50903`
- eligible_contracts: `44359`
- market_executable_contracts: `25058`
- snapshot_candidates: `25058`
- candidate_pool: `611`
- location_executable: `249`
- feasible: `168`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `157`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19067`
- MARKET_INELIGIBLE_SINGLETON: `6510`
- UNSAFE_OR_UNVERIFIED_LOCATION: `362`
- HIGHSEC_RESTRICTED_CAPITAL: `73`
- SKIN_DOMINANT: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `2`
