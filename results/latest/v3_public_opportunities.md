# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T11:31:57.288Z
- Market snapshot: 2026-10-11T11:48:39.555Z
- Candidate universe: 24555; deep validation pool: 261; feasible: 183
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 159
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

- raw_contracts: `50294`
- eligible_contracts: `43726`
- market_executable_contracts: `24555`
- snapshot_candidates: `24555`
- candidate_pool: `610`
- location_executable: `261`
- feasible: `183`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18942`
- MARKET_INELIGIBLE_SINGLETON: `6227`
- UNSAFE_OR_UNVERIFIED_LOCATION: `349`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- SKIN_DOMINANT: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `5`
- LIST_DATA_INCOMPLETE: `4`
