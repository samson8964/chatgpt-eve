# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-07T05:31:18.656Z
- Market snapshot: 2026-10-07T05:48:23.261Z
- Candidate universe: 24599; deep validation pool: 251; feasible: 178
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 158
- FORMAL MAIL: 0

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49636`
- eligible_contracts: `43214`
- market_executable_contracts: `24599`
- snapshot_candidates: `24599`
- candidate_pool: `605`
- location_executable: `251`
- feasible: `178`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `158`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18389`
- MARKET_INELIGIBLE_SINGLETON: `5997`
- UNSAFE_OR_UNVERIFIED_LOCATION: `354`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- LIST_UNSUPPORTED: `8`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `4`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
