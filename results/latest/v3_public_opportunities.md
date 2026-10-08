# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T16:01:40.716Z
- Market snapshot: 2026-10-08T16:48:48.728Z
- Candidate universe: 24529; deep validation pool: 244; feasible: 173
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 159
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

- raw_contracts: `50090`
- eligible_contracts: `43494`
- market_executable_contracts: `24529`
- snapshot_candidates: `24529`
- candidate_pool: `606`
- location_executable: `244`
- feasible: `173`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `159`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18739`
- MARKET_INELIGIBLE_SINGLETON: `6089`
- UNSAFE_OR_UNVERIFIED_LOCATION: `362`
- HIGHSEC_RESTRICTED_CAPITAL: `67`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- SKIN_DOMINANT: `4`
- LIST_DATA_INCOMPLETE: `4`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
