# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T12:31:59.708Z
- Market snapshot: 2026-10-10T12:18:35.376Z
- Candidate universe: 24696; deep validation pool: 258; feasible: 184
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 13
- RESEARCH: 154
- FORMAL MAIL: 3

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50360`
- eligible_contracts: `43781`
- market_executable_contracts: `24696`
- snapshot_candidates: `24696`
- candidate_pool: `610`
- location_executable: `258`
- feasible: `184`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `13`
- research_watch: `154`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18865`
- MARKET_INELIGIBLE_SINGLETON: `6258`
- UNSAFE_OR_UNVERIFIED_LOCATION: `352`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `5`
