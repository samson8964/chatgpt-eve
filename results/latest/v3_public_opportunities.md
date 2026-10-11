# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T12:01:38.068Z
- Market snapshot: 2026-10-11T12:18:34.860Z
- Candidate universe: 24538; deep validation pool: 252; feasible: 180
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 159
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

- raw_contracts: `50260`
- eligible_contracts: `43706`
- market_executable_contracts: `24538`
- snapshot_candidates: `24538`
- candidate_pool: `610`
- location_executable: `252`
- feasible: `180`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18941`
- MARKET_INELIGIBLE_SINGLETON: `6219`
- UNSAFE_OR_UNVERIFIED_LOCATION: `358`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- FATAL_OR_ACCESS_UNVERIFIED: `11`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
- LIST_DATA_INCOMPLETE: `5`
- SKIN_DOMINANT: `4`
