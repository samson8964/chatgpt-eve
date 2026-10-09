# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T12:31:42.266Z
- Market snapshot: 2026-10-09T12:49:04.524Z
- Candidate universe: 24380; deep validation pool: 246; feasible: 180
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 153
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

- raw_contracts: `50264`
- eligible_contracts: `43533`
- market_executable_contracts: `24380`
- snapshot_candidates: `24380`
- candidate_pool: `610`
- location_executable: `246`
- feasible: `180`
- full_cash: `4`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `11`
- research_watch: `153`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18937`
- MARKET_INELIGIBLE_SINGLETON: `6220`
- UNSAFE_OR_UNVERIFIED_LOCATION: `364`
- HIGHSEC_RESTRICTED_CAPITAL: `61`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- BARTER_PROCUREMENT_INCOMPLETE: `9`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `3`
- NO_EXECUTABLE_ITEMS: `2`
