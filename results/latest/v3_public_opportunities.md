# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-13T02:01:37.592Z
- Market snapshot: 2026-10-13T02:18:27.073Z
- Candidate universe: 25091; deep validation pool: 254; feasible: 173
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 149
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

- raw_contracts: `50726`
- eligible_contracts: `44491`
- market_executable_contracts: `25091`
- snapshot_candidates: `25091`
- candidate_pool: `612`
- location_executable: `254`
- feasible: `173`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `149`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19177`
- MARKET_INELIGIBLE_SINGLETON: `6437`
- UNSAFE_OR_UNVERIFIED_LOCATION: `358`
- HIGHSEC_RESTRICTED_CAPITAL: `73`
- FATAL_OR_ACCESS_UNVERIFIED: `18`
- SKIN_DOMINANT: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
