# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T23:01:38.890Z
- Market snapshot: 2026-10-12T23:18:41.645Z
- Candidate universe: 25084; deep validation pool: 264; feasible: 148
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 3
- RESEARCH: 137
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

- raw_contracts: `50722`
- eligible_contracts: `44447`
- market_executable_contracts: `25084`
- snapshot_candidates: `25084`
- candidate_pool: `612`
- location_executable: `264`
- feasible: `148`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `3`
- research_watch: `137`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19131`
- MARKET_INELIGIBLE_SINGLETON: `6467`
- UNSAFE_OR_UNVERIFIED_LOCATION: `348`
- HIGHSEC_RESTRICTED_CAPITAL: `110`
- LIST_DATA_INCOMPLETE: `10`
- SKIN_DOMINANT: `6`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- LIST_TOO_SLOW: `5`
