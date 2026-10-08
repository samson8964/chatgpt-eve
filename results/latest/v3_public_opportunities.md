# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T03:31:37.161Z
- Market snapshot: 2026-10-08T03:18:23.420Z
- Candidate universe: 24535; deep validation pool: 255; feasible: 233
- FULL_CASH: 6
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 156
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

- raw_contracts: `49899`
- eligible_contracts: `43365`
- market_executable_contracts: `24535`
- snapshot_candidates: `24535`
- candidate_pool: `605`
- location_executable: `255`
- feasible: `233`
- full_cash: `6`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `6`
- research_watch: `156`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18604`
- MARKET_INELIGIBLE_SINGLETON: `5995`
- UNSAFE_OR_UNVERIFIED_LOCATION: `350`
- HIGHSEC_RESTRICTED_CAPITAL: `18`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
