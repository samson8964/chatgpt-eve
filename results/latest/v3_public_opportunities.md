# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T20:01:20.435Z
- Market snapshot: 2026-10-07T20:18:22.770Z
- Candidate universe: 24549; deep validation pool: 221; feasible: 162
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 147
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

- raw_contracts: `49922`
- eligible_contracts: `43382`
- market_executable_contracts: `24549`
- snapshot_candidates: `24549`
- candidate_pool: `605`
- location_executable: `221`
- feasible: `162`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `147`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18612`
- MARKET_INELIGIBLE_SINGLETON: `5985`
- UNSAFE_OR_UNVERIFIED_LOCATION: `384`
- HIGHSEC_RESTRICTED_CAPITAL: `55`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
