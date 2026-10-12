# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T05:31:37.833Z
- Market snapshot: 2026-10-12T05:18:24.901Z
- Candidate universe: 25050; deep validation pool: 249; feasible: 174
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 162
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

- raw_contracts: `50866`
- eligible_contracts: `44390`
- market_executable_contracts: `25050`
- snapshot_candidates: `25050`
- candidate_pool: `611`
- location_executable: `249`
- feasible: `174`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `162`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19109`
- MARKET_INELIGIBLE_SINGLETON: `6523`
- UNSAFE_OR_UNVERIFIED_LOCATION: `362`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- LIST_DATA_INCOMPLETE: `7`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `5`
