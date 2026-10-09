# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T17:01:24.839Z
- Market snapshot: 2026-10-09T16:48:38.900Z
- Candidate universe: 24383; deep validation pool: 255; feasible: 236
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 2
- BARTER: 0
- LIST-SUPPORTED: 8
- RESEARCH: 159
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

- raw_contracts: `50222`
- eligible_contracts: `43484`
- market_executable_contracts: `24383`
- snapshot_candidates: `24383`
- candidate_pool: `610`
- location_executable: `255`
- feasible: `236`
- full_cash: `4`
- partial_cash_floor: `2`
- barter: `0`
- list_supported: `8`
- research_watch: `159`
- mail_eligible: `4`

## Rejection reasons

- BPC_ROUTED: `18894`
- MARKET_INELIGIBLE_SINGLETON: `6179`
- UNSAFE_OR_UNVERIFIED_LOCATION: `355`
- HIGHSEC_RESTRICTED_CAPITAL: `17`
- FATAL_OR_ACCESS_UNVERIFIED: `13`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `6`
- LIST_DATA_INCOMPLETE: `4`
- SKIN_DOMINANT: `2`
