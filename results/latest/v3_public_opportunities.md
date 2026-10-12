# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T21:01:42.331Z
- Market snapshot: 2026-10-12T20:48:40.055Z
- Candidate universe: 25031; deep validation pool: 253; feasible: 165
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 2
- RESEARCH: 155
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

- raw_contracts: `50728`
- eligible_contracts: `44315`
- market_executable_contracts: `25031`
- snapshot_candidates: `25031`
- candidate_pool: `611`
- location_executable: `253`
- feasible: `165`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `2`
- research_watch: `155`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19053`
- MARKET_INELIGIBLE_SINGLETON: `6490`
- UNSAFE_OR_UNVERIFIED_LOCATION: `358`
- HIGHSEC_RESTRICTED_CAPITAL: `84`
- LIST_DATA_INCOMPLETE: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `4`
