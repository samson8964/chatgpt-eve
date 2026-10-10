# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T03:31:36.736Z
- Market snapshot: 2026-10-10T03:48:24.929Z
- Candidate universe: 24680; deep validation pool: 268; feasible: 193
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
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

- raw_contracts: `50428`
- eligible_contracts: `43749`
- market_executable_contracts: `24680`
- snapshot_candidates: `24680`
- candidate_pool: `609`
- location_executable: `268`
- feasible: `193`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `157`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18858`
- MARKET_INELIGIBLE_SINGLETON: `6281`
- UNSAFE_OR_UNVERIFIED_LOCATION: `341`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `3`
- LIST_TOO_SLOW: `3`
