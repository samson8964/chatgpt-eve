# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T13:01:48.767Z
- Market snapshot: 2026-10-09T12:49:04.524Z
- Candidate universe: 24393; deep validation pool: 248; feasible: 183
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 163
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

- raw_contracts: `50288`
- eligible_contracts: `43591`
- market_executable_contracts: `24393`
- snapshot_candidates: `24393`
- candidate_pool: `610`
- location_executable: `248`
- feasible: `183`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `163`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18978`
- MARKET_INELIGIBLE_SINGLETON: `6234`
- UNSAFE_OR_UNVERIFIED_LOCATION: `362`
- HIGHSEC_RESTRICTED_CAPITAL: `61`
- FATAL_OR_ACCESS_UNVERIFIED: `12`
- BARTER_PROCUREMENT_INCOMPLETE: `9`
- LIST_DATA_INCOMPLETE: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
