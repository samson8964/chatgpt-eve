# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T15:32:24.941Z
- Market snapshot: 2026-10-12T15:48:37.479Z
- Candidate universe: 24999; deep validation pool: 236; feasible: 159
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 147
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

- raw_contracts: `50744`
- eligible_contracts: `44307`
- market_executable_contracts: `24999`
- snapshot_candidates: `24999`
- candidate_pool: `611`
- location_executable: `236`
- feasible: `159`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `147`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19081`
- MARKET_INELIGIBLE_SINGLETON: `6524`
- UNSAFE_OR_UNVERIFIED_LOCATION: `375`
- HIGHSEC_RESTRICTED_CAPITAL: `70`
- SKIN_DOMINANT: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `4`
