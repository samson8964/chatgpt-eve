# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T16:31:25.182Z
- Market snapshot: 2026-10-09T16:48:38.900Z
- Candidate universe: 24365; deep validation pool: 270; feasible: 198
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 163
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

- raw_contracts: `50218`
- eligible_contracts: `43520`
- market_executable_contracts: `24365`
- snapshot_candidates: `24365`
- candidate_pool: `610`
- location_executable: `270`
- feasible: `198`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `163`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18947`
- MARKET_INELIGIBLE_SINGLETON: `6179`
- UNSAFE_OR_UNVERIFIED_LOCATION: `340`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- FATAL_OR_ACCESS_UNVERIFIED: `14`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_UNSUPPORTED: `1`
