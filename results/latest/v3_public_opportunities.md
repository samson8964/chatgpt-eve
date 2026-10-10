# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T22:01:37.087Z
- Market snapshot: 2026-10-10T22:18:39.554Z
- Candidate universe: 24771; deep validation pool: 289; feasible: 215
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 155
- FORMAL MAIL: 2

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50461`
- eligible_contracts: `43862`
- market_executable_contracts: `24771`
- snapshot_candidates: `24771`
- candidate_pool: `610`
- location_executable: `289`
- feasible: `215`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `11`
- research_watch: `155`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `18868`
- MARKET_INELIGIBLE_SINGLETON: `6384`
- UNSAFE_OR_UNVERIFIED_LOCATION: `321`
- HIGHSEC_RESTRICTED_CAPITAL: `73`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
- SKIN_DOMINANT: `1`
