# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T02:31:36.244Z
- Market snapshot: 2026-10-09T02:18:19.743Z
- Candidate universe: 24341; deep validation pool: 267; feasible: 195
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
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

- raw_contracts: `50085`
- eligible_contracts: `43359`
- market_executable_contracts: `24341`
- snapshot_candidates: `24341`
- candidate_pool: `607`
- location_executable: `267`
- feasible: `195`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `157`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18795`
- MARKET_INELIGIBLE_SINGLETON: `6043`
- UNSAFE_OR_UNVERIFIED_LOCATION: `340`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
