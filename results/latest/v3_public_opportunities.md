# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T15:01:22.653Z
- Market snapshot: 2026-10-07T15:18:28.288Z
- Candidate universe: 24481; deep validation pool: 250; feasible: 185
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 158
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

- raw_contracts: `49821`
- eligible_contracts: `43231`
- market_executable_contracts: `24481`
- snapshot_candidates: `24481`
- candidate_pool: `605`
- location_executable: `250`
- feasible: `185`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `158`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18528`
- MARKET_INELIGIBLE_SINGLETON: `6000`
- UNSAFE_OR_UNVERIFIED_LOCATION: `355`
- HIGHSEC_RESTRICTED_CAPITAL: `61`
- FATAL_OR_ACCESS_UNVERIFIED: `17`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
