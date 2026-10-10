# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T23:01:39.431Z
- Market snapshot: 2026-10-10T23:18:35.702Z
- Candidate universe: 24654; deep validation pool: 298; feasible: 222
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 157
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

- raw_contracts: `50358`
- eligible_contracts: `43782`
- market_executable_contracts: `24654`
- snapshot_candidates: `24654`
- candidate_pool: `610`
- location_executable: `298`
- feasible: `222`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `157`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18902`
- MARKET_INELIGIBLE_SINGLETON: `6285`
- UNSAFE_OR_UNVERIFIED_LOCATION: `312`
- HIGHSEC_RESTRICTED_CAPITAL: `73`
- FATAL_OR_ACCESS_UNVERIFIED: `13`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `3`
