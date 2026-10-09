# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T03:01:28.368Z
- Market snapshot: 2026-10-09T02:48:20.724Z
- Candidate universe: 24335; deep validation pool: 270; feasible: 208
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
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

- raw_contracts: `50087`
- eligible_contracts: `43345`
- market_executable_contracts: `24335`
- snapshot_candidates: `24335`
- candidate_pool: `607`
- location_executable: `270`
- feasible: `208`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `158`
- mail_eligible: `3`

## Rejection reasons

- BPC_ROUTED: `18787`
- MARKET_INELIGIBLE_SINGLETON: `6044`
- UNSAFE_OR_UNVERIFIED_LOCATION: `337`
- HIGHSEC_RESTRICTED_CAPITAL: `60`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `2`
