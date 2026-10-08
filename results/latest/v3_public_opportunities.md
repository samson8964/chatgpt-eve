# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T21:31:59.995Z
- Market snapshot: 2026-10-08T21:18:31.053Z
- Candidate universe: 24392; deep validation pool: 247; feasible: 228
- FULL_CASH: 6
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 155
- FORMAL MAIL: 6

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50136`
- eligible_contracts: `43468`
- market_executable_contracts: `24392`
- snapshot_candidates: `24392`
- candidate_pool: `607`
- location_executable: `247`
- feasible: `228`
- full_cash: `6`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `155`
- mail_eligible: `6`

## Rejection reasons

- BPC_ROUTED: `18851`
- MARKET_INELIGIBLE_SINGLETON: `6074`
- UNSAFE_OR_UNVERIFIED_LOCATION: `360`
- HIGHSEC_RESTRICTED_CAPITAL: `17`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- SKIN_DOMINANT: `2`
