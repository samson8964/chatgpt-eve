# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T06:31:28.810Z
- Market snapshot: 2026-10-09T06:49:03.020Z
- Candidate universe: 24208; deep validation pool: 242; feasible: 219
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 9
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

- raw_contracts: `50070`
- eligible_contracts: `43240`
- market_executable_contracts: `24208`
- snapshot_candidates: `24208`
- candidate_pool: `607`
- location_executable: `242`
- feasible: `219`
- full_cash: `1`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `9`
- research_watch: `154`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18816`
- MARKET_INELIGIBLE_SINGLETON: `6042`
- UNSAFE_OR_UNVERIFIED_LOCATION: `365`
- HIGHSEC_RESTRICTED_CAPITAL: `16`
- FATAL_OR_ACCESS_UNVERIFIED: `13`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_DATA_INCOMPLETE: `3`
- NO_EXECUTABLE_ITEMS: `2`
