# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T04:02:01.129Z
- Market snapshot: 2026-10-10T04:18:22.750Z
- Candidate universe: 24671; deep validation pool: 262; feasible: 187
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 2
- BARTER: 0
- LIST-SUPPORTED: 12
- RESEARCH: 154
- FORMAL MAIL: 4

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50429`
- eligible_contracts: `43733`
- market_executable_contracts: `24671`
- snapshot_candidates: `24671`
- candidate_pool: `609`
- location_executable: `262`
- feasible: `187`
- full_cash: `2`
- partial_cash_floor: `2`
- barter: `0`
- list_supported: `12`
- research_watch: `154`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18848`
- MARKET_INELIGIBLE_SINGLETON: `6279`
- UNSAFE_OR_UNVERIFIED_LOCATION: `347`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `1`
