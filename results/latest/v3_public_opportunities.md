# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T02:01:37.328Z
- Market snapshot: 2026-10-09T01:48:23.747Z
- Candidate universe: 24346; deep validation pool: 268; feasible: 211
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 158
- FORMAL MAIL: 4

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50107`
- eligible_contracts: `43390`
- market_executable_contracts: `24346`
- snapshot_candidates: `24346`
- candidate_pool: `607`
- location_executable: `268`
- feasible: `211`
- full_cash: `4`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `6`
- research_watch: `158`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18820`
- MARKET_INELIGIBLE_SINGLETON: `6046`
- UNSAFE_OR_UNVERIFIED_LOCATION: `339`
- HIGHSEC_RESTRICTED_CAPITAL: `54`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
