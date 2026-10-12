# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T02:31:40.256Z
- Market snapshot: 2026-10-12T02:18:35.894Z
- Candidate universe: 25019; deep validation pool: 256; feasible: 179
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 8
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

- raw_contracts: `50881`
- eligible_contracts: `44295`
- market_executable_contracts: `25019`
- snapshot_candidates: `25019`
- candidate_pool: `611`
- location_executable: `256`
- feasible: `179`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `8`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19040`
- MARKET_INELIGIBLE_SINGLETON: `6505`
- UNSAFE_OR_UNVERIFIED_LOCATION: `355`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- SKIN_DOMINANT: `6`
- LIST_DATA_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
