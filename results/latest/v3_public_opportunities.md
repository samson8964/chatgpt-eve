# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T03:01:33.880Z
- Market snapshot: 2026-10-10T02:48:26.323Z
- Candidate universe: 24683; deep validation pool: 270; feasible: 197
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
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

- raw_contracts: `50436`
- eligible_contracts: `43767`
- market_executable_contracts: `24683`
- snapshot_candidates: `24683`
- candidate_pool: `610`
- location_executable: `270`
- feasible: `197`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `158`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18872`
- MARKET_INELIGIBLE_SINGLETON: `6286`
- UNSAFE_OR_UNVERIFIED_LOCATION: `340`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `3`
