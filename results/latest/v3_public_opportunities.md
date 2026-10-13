# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-13T00:31:42.889Z
- Market snapshot: 2026-10-13T00:18:32.232Z
- Candidate universe: 25079; deep validation pool: 276; feasible: 172
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 154
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

- raw_contracts: `50732`
- eligible_contracts: `44481`
- market_executable_contracts: `25079`
- snapshot_candidates: `25079`
- candidate_pool: `611`
- location_executable: `276`
- feasible: `172`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `154`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19170`
- MARKET_INELIGIBLE_SINGLETON: `6475`
- UNSAFE_OR_UNVERIFIED_LOCATION: `335`
- HIGHSEC_RESTRICTED_CAPITAL: `100`
- LIST_DATA_INCOMPLETE: `12`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `4`
