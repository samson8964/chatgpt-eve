# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T12:31:26.608Z
- Market snapshot: 2026-10-08T12:18:39.320Z
- Candidate universe: 24572; deep validation pool: 273; feasible: 205
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
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

- raw_contracts: `49971`
- eligible_contracts: `43397`
- market_executable_contracts: `24572`
- snapshot_candidates: `24572`
- candidate_pool: `606`
- location_executable: `273`
- feasible: `205`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `154`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18595`
- MARKET_INELIGIBLE_SINGLETON: `6055`
- UNSAFE_OR_UNVERIFIED_LOCATION: `333`
- HIGHSEC_RESTRICTED_CAPITAL: `66`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- SKIN_DOMINANT: `2`
- LIST_TOO_SLOW: `2`
