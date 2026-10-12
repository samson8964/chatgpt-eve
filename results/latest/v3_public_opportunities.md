# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T07:31:58.708Z
- Market snapshot: 2026-10-12T07:18:37.913Z
- Candidate universe: 25045; deep validation pool: 251; feasible: 188
- FULL_CASH: 3
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 166
- FORMAL MAIL: 2

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50877`
- eligible_contracts: `44351`
- market_executable_contracts: `25045`
- snapshot_candidates: `25045`
- candidate_pool: `611`
- location_executable: `251`
- feasible: `188`
- full_cash: `3`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `166`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19073`
- MARKET_INELIGIBLE_SINGLETON: `6502`
- UNSAFE_OR_UNVERIFIED_LOCATION: `360`
- HIGHSEC_RESTRICTED_CAPITAL: `59`
- BARTER_PROCUREMENT_INCOMPLETE: `10`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- SKIN_DOMINANT: `4`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `3`
