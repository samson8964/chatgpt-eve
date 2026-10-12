# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T10:01:44.254Z
- Market snapshot: 2026-10-12T09:48:37.091Z
- Candidate universe: 25085; deep validation pool: 253; feasible: 176
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 160
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

- raw_contracts: `50841`
- eligible_contracts: `44367`
- market_executable_contracts: `25085`
- snapshot_candidates: `25085`
- candidate_pool: `610`
- location_executable: `253`
- feasible: `176`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `160`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19053`
- MARKET_INELIGIBLE_SINGLETON: `6480`
- UNSAFE_OR_UNVERIFIED_LOCATION: `357`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- LIST_DATA_INCOMPLETE: `7`
- SKIN_DOMINANT: `6`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- LIST_TOO_SLOW: `5`
