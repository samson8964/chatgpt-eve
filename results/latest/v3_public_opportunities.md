# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T14:01:23.153Z
- Market snapshot: 2026-10-08T14:18:35.224Z
- Candidate universe: 24564; deep validation pool: 230; feasible: 165
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 145
- FORMAL MAIL: 0

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50045`
- eligible_contracts: `43453`
- market_executable_contracts: `24564`
- snapshot_candidates: `24564`
- candidate_pool: `606`
- location_executable: `230`
- feasible: `165`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `145`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18664`
- MARKET_INELIGIBLE_SINGLETON: `6064`
- UNSAFE_OR_UNVERIFIED_LOCATION: `376`
- HIGHSEC_RESTRICTED_CAPITAL: `62`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- LIST_DATA_INCOMPLETE: `5`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
