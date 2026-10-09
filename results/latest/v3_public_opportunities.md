# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T11:31:50.731Z
- Market snapshot: 2026-10-09T11:19:33.177Z
- Candidate universe: 24397; deep validation pool: 233; feasible: 177
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 155
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

- raw_contracts: `50243`
- eligible_contracts: `43554`
- market_executable_contracts: `24397`
- snapshot_candidates: `24397`
- candidate_pool: `610`
- location_executable: `233`
- feasible: `177`
- full_cash: `1`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `11`
- research_watch: `155`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18934`
- MARKET_INELIGIBLE_SINGLETON: `6232`
- UNSAFE_OR_UNVERIFIED_LOCATION: `377`
- HIGHSEC_RESTRICTED_CAPITAL: `54`
- BARTER_PROCUREMENT_INCOMPLETE: `9`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `2`
