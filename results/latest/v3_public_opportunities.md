# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T10:31:36.387Z
- Market snapshot: 2026-10-11T10:48:37.134Z
- Candidate universe: 24570; deep validation pool: 242; feasible: 166
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 2
- RESEARCH: 73
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

- raw_contracts: `50311`
- eligible_contracts: `43790`
- market_executable_contracts: `24570`
- snapshot_candidates: `24570`
- candidate_pool: `610`
- location_executable: `242`
- feasible: `166`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `2`
- research_watch: `73`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18992`
- MARKET_INELIGIBLE_SINGLETON: `6234`
- UNSAFE_OR_UNVERIFIED_LOCATION: `368`
- FATAL_OR_ACCESS_UNVERIFIED: `90`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- SKIN_DOMINANT: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `1`
