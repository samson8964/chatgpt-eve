# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T14:01:42.501Z
- Market snapshot: 2026-10-12T13:48:39.790Z
- Candidate universe: 25022; deep validation pool: 248; feasible: 171
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 155
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

- raw_contracts: `50776`
- eligible_contracts: `44340`
- market_executable_contracts: `25022`
- snapshot_candidates: `25022`
- candidate_pool: `612`
- location_executable: `248`
- feasible: `171`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `155`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19090`
- MARKET_INELIGIBLE_SINGLETON: `6538`
- UNSAFE_OR_UNVERIFIED_LOCATION: `364`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_DATA_INCOMPLETE: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- NO_EXECUTABLE_ITEMS: `1`
