# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T01:31:38.550Z
- Market snapshot: 2026-10-10T01:48:30.485Z
- Candidate universe: 24692; deep validation pool: 298; feasible: 233
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 12
- RESEARCH: 158
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

- raw_contracts: `50445`
- eligible_contracts: `43779`
- market_executable_contracts: `24692`
- snapshot_candidates: `24692`
- candidate_pool: `610`
- location_executable: `298`
- feasible: `233`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `12`
- research_watch: `158`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18874`
- MARKET_INELIGIBLE_SINGLETON: `6281`
- UNSAFE_OR_UNVERIFIED_LOCATION: `312`
- HIGHSEC_RESTRICTED_CAPITAL: `60`
- BARTER_PROCUREMENT_INCOMPLETE: `10`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `2`
