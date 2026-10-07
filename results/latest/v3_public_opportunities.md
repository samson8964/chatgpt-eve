# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T10:31:20.726Z
- Market snapshot: 2026-10-07T10:48:28.592Z
- Candidate universe: 24527; deep validation pool: 222; feasible: 147
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 2
- RESEARCH: 127
- FORMAL MAIL: 0

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49739`
- eligible_contracts: `43242`
- market_executable_contracts: `24527`
- snapshot_candidates: `24527`
- candidate_pool: `605`
- location_executable: `222`
- feasible: `147`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `2`
- research_watch: `127`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18490`
- MARKET_INELIGIBLE_SINGLETON: `5988`
- UNSAFE_OR_UNVERIFIED_LOCATION: `383`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- FATAL_OR_ACCESS_UNVERIFIED: `17`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
- LIST_UNSUPPORTED: `2`
