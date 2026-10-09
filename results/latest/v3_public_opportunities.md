# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T05:31:37.517Z
- Market snapshot: 2026-10-09T05:48:24.320Z
- Candidate universe: 24275; deep validation pool: 242; feasible: 173
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 14
- RESEARCH: 143
- FORMAL MAIL: 4

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50081`
- eligible_contracts: `43312`
- market_executable_contracts: `24275`
- snapshot_candidates: `24275`
- candidate_pool: `607`
- location_executable: `242`
- feasible: `173`
- full_cash: `5`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `14`
- research_watch: `143`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18814`
- MARKET_INELIGIBLE_SINGLETON: `6039`
- UNSAFE_OR_UNVERIFIED_LOCATION: `365`
- HIGHSEC_RESTRICTED_CAPITAL: `67`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- LIST_DATA_INCOMPLETE: `5`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `2`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
