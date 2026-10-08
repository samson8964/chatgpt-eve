# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T18:31:32.738Z
- Market snapshot: 2026-10-08T18:18:47.365Z
- Candidate universe: 24381; deep validation pool: 255; feasible: 230
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 2
- RESEARCH: 160
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

- raw_contracts: `50135`
- eligible_contracts: `43410`
- market_executable_contracts: `24381`
- snapshot_candidates: `24381`
- candidate_pool: `607`
- location_executable: `255`
- feasible: `230`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `2`
- research_watch: `160`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18805`
- MARKET_INELIGIBLE_SINGLETON: `6107`
- UNSAFE_OR_UNVERIFIED_LOCATION: `352`
- HIGHSEC_RESTRICTED_CAPITAL: `20`
- FATAL_OR_ACCESS_UNVERIFIED: `14`
- SKIN_DOMINANT: `5`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
