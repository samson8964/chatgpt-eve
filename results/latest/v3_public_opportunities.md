# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T17:01:44.501Z
- Market snapshot: 2026-10-12T17:18:39.065Z
- Candidate universe: 25035; deep validation pool: 234; feasible: 162
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 138
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

- raw_contracts: `50788`
- eligible_contracts: `44270`
- market_executable_contracts: `25035`
- snapshot_candidates: `25035`
- candidate_pool: `611`
- location_executable: `234`
- feasible: `162`
- full_cash: `1`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `4`
- research_watch: `138`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19008`
- MARKET_INELIGIBLE_SINGLETON: `6509`
- UNSAFE_OR_UNVERIFIED_LOCATION: `377`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- FATAL_OR_ACCESS_UNVERIFIED: `18`
- SKIN_DOMINANT: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `5`
- LIST_DATA_INCOMPLETE: `5`
