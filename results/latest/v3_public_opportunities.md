# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T04:01:36.053Z
- Market snapshot: 2026-10-09T04:18:23.633Z
- Candidate universe: 24309; deep validation pool: 272; feasible: 216
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 158
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

- raw_contracts: `50083`
- eligible_contracts: `43351`
- market_executable_contracts: `24309`
- snapshot_candidates: `24309`
- candidate_pool: `607`
- location_executable: `272`
- feasible: `216`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `158`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18819`
- MARKET_INELIGIBLE_SINGLETON: `6029`
- UNSAFE_OR_UNVERIFIED_LOCATION: `335`
- HIGHSEC_RESTRICTED_CAPITAL: `52`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- BARTER_PROCUREMENT_INCOMPLETE: `5`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
