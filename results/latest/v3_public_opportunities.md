# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T07:02:51.992Z
- Market snapshot: 2026-10-09T06:49:03.020Z
- Candidate universe: 24194; deep validation pool: 247; feasible: 192
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
- RESEARCH: 159
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

- raw_contracts: `50068`
- eligible_contracts: `43242`
- market_executable_contracts: `24194`
- snapshot_candidates: `24194`
- candidate_pool: `607`
- location_executable: `247`
- feasible: `192`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18826`
- MARKET_INELIGIBLE_SINGLETON: `6041`
- UNSAFE_OR_UNVERIFIED_LOCATION: `360`
- HIGHSEC_RESTRICTED_CAPITAL: `51`
- FATAL_OR_ACCESS_UNVERIFIED: `12`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `3`
