# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T10:32:15.776Z
- Market snapshot: 2026-10-12T10:18:35.987Z
- Candidate universe: 25114; deep validation pool: 253; feasible: 178
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 160
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

- raw_contracts: `50854`
- eligible_contracts: `44370`
- market_executable_contracts: `25114`
- snapshot_candidates: `25114`
- candidate_pool: `611`
- location_executable: `253`
- feasible: `178`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `160`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19027`
- MARKET_INELIGIBLE_SINGLETON: `6502`
- UNSAFE_OR_UNVERIFIED_LOCATION: `358`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `6`
- LIST_TOO_SLOW: `6`
- LIST_DATA_INCOMPLETE: `4`
