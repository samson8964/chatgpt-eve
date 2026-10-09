# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T12:31:42.266Z
- Market snapshot: 2026-10-09T12:18:39.981Z
- Candidate universe: 24374; deep validation pool: 246; feasible: 174
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 152
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

- raw_contracts: `50264`
- eligible_contracts: `43534`
- market_executable_contracts: `24374`
- snapshot_candidates: `24374`
- candidate_pool: `610`
- location_executable: `246`
- feasible: `174`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `152`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18938`
- MARKET_INELIGIBLE_SINGLETON: `6226`
- UNSAFE_OR_UNVERIFIED_LOCATION: `364`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- FATAL_OR_ACCESS_UNVERIFIED: `12`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_DATA_INCOMPLETE: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `1`
