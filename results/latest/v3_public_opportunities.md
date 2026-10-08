# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T22:01:42.235Z
- Market snapshot: 2026-10-08T21:48:28.672Z
- Candidate universe: 24392; deep validation pool: 243; feasible: 185
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 158
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

- raw_contracts: `50126`
- eligible_contracts: `43454`
- market_executable_contracts: `24392`
- snapshot_candidates: `24392`
- candidate_pool: `607`
- location_executable: `243`
- feasible: `185`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `158`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18842`
- MARKET_INELIGIBLE_SINGLETON: `6068`
- UNSAFE_OR_UNVERIFIED_LOCATION: `364`
- HIGHSEC_RESTRICTED_CAPITAL: `54`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- SKIN_DOMINANT: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `4`
- LIST_DATA_INCOMPLETE: `4`
- LIST_TOO_SLOW: `3`
