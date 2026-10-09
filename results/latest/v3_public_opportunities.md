# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T00:01:33.647Z
- Market snapshot: 2026-10-08T23:48:28.663Z
- Candidate universe: 24356; deep validation pool: 242; feasible: 187
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 154
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

- raw_contracts: `50103`
- eligible_contracts: `43458`
- market_executable_contracts: `24356`
- snapshot_candidates: `24356`
- candidate_pool: `607`
- location_executable: `242`
- feasible: `187`
- full_cash: `2`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `10`
- research_watch: `154`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18877`
- MARKET_INELIGIBLE_SINGLETON: `6047`
- UNSAFE_OR_UNVERIFIED_LOCATION: `365`
- HIGHSEC_RESTRICTED_CAPITAL: `51`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- SKIN_DOMINANT: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `3`
