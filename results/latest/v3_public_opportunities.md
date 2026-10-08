# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T20:01:21.948Z
- Market snapshot: 2026-10-08T18:48:53.568Z
- Candidate universe: 24410; deep validation pool: 250; feasible: 187
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 4
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

- raw_contracts: `50161`
- eligible_contracts: `43460`
- market_executable_contracts: `24410`
- snapshot_candidates: `24410`
- candidate_pool: `607`
- location_executable: `250`
- feasible: `187`
- full_cash: `1`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `4`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18827`
- MARKET_INELIGIBLE_SINGLETON: `6097`
- UNSAFE_OR_UNVERIFIED_LOCATION: `357`
- HIGHSEC_RESTRICTED_CAPITAL: `59`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- SKIN_DOMINANT: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
- LIST_DATA_INCOMPLETE: `3`
