# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T08:31:42.933Z
- Market snapshot: 2026-10-11T08:48:38.900Z
- Candidate universe: 24548; deep validation pool: 264; feasible: 184
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
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

- raw_contracts: `50239`
- eligible_contracts: `43782`
- market_executable_contracts: `24548`
- snapshot_candidates: `24548`
- candidate_pool: `610`
- location_executable: `264`
- feasible: `184`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19008`
- MARKET_INELIGIBLE_SINGLETON: `6256`
- UNSAFE_OR_UNVERIFIED_LOCATION: `346`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- FATAL_OR_ACCESS_UNVERIFIED: `15`
- SKIN_DOMINANT: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
