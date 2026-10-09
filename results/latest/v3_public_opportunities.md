# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T19:31:27.097Z
- Market snapshot: 2026-10-09T19:48:32.450Z
- Candidate universe: 24515; deep validation pool: 251; feasible: 178
- FULL_CASH: 7
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 157
- FORMAL MAIL: 5

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50240`
- eligible_contracts: `43574`
- market_executable_contracts: `24515`
- snapshot_candidates: `24515`
- candidate_pool: `610`
- location_executable: `251`
- feasible: `178`
- full_cash: `7`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `157`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18845`
- MARKET_INELIGIBLE_SINGLETON: `6181`
- UNSAFE_OR_UNVERIFIED_LOCATION: `359`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_DATA_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `1`
