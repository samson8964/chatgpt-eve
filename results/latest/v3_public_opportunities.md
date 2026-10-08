# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T04:01:35.457Z
- Market snapshot: 2026-10-08T04:18:25.484Z
- Candidate universe: 24535; deep validation pool: 250; feasible: 235
- FULL_CASH: 8
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 156
- FORMAL MAIL: 7

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `49894`
- eligible_contracts: `43364`
- market_executable_contracts: `24535`
- snapshot_candidates: `24535`
- candidate_pool: `605`
- location_executable: `250`
- feasible: `235`
- full_cash: `8`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `7`
- research_watch: `156`
- mail_eligible: `7`

## Rejection reasons

- BPC_ROUTED: `18603`
- MARKET_INELIGIBLE_SINGLETON: `5995`
- UNSAFE_OR_UNVERIFIED_LOCATION: `355`
- HIGHSEC_RESTRICTED_CAPITAL: `13`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
- BARTER_PROCUREMENT_INCOMPLETE: `3`
- LIST_TOO_SLOW: `3`
- SKIN_DOMINANT: `2`
