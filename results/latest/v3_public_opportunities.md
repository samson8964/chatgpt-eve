# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T06:31:53.654Z
- Market snapshot: 2026-10-08T06:49:02.275Z
- Candidate universe: 24553; deep validation pool: 231; feasible: 214
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 153
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

- raw_contracts: `49818`
- eligible_contracts: `43285`
- market_executable_contracts: `24553`
- snapshot_candidates: `24553`
- candidate_pool: `605`
- location_executable: `231`
- feasible: `214`
- full_cash: `4`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `9`
- research_watch: `153`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18504`
- MARKET_INELIGIBLE_SINGLETON: `5996`
- UNSAFE_OR_UNVERIFIED_LOCATION: `374`
- HIGHSEC_RESTRICTED_CAPITAL: `14`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- LIST_DATA_INCOMPLETE: `2`
