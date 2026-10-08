# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T12:01:40.016Z
- Market snapshot: 2026-10-08T11:48:36.310Z
- Candidate universe: 24560; deep validation pool: 232; feasible: 161
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 142
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

- raw_contracts: `49913`
- eligible_contracts: `43372`
- market_executable_contracts: `24560`
- snapshot_candidates: `24560`
- candidate_pool: `606`
- location_executable: `232`
- feasible: `161`
- full_cash: `3`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `11`
- research_watch: `142`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18582`
- MARKET_INELIGIBLE_SINGLETON: `6016`
- UNSAFE_OR_UNVERIFIED_LOCATION: `374`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- LIST_DATA_INCOMPLETE: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
