# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-13T03:01:39.920Z
- Market snapshot: 2026-10-13T02:48:27.966Z
- Candidate universe: 25055; deep validation pool: 264; feasible: 182
- FULL_CASH: 4
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 7
- RESEARCH: 151
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

- raw_contracts: `50682`
- eligible_contracts: `44478`
- market_executable_contracts: `25055`
- snapshot_candidates: `25055`
- candidate_pool: `612`
- location_executable: `264`
- feasible: `182`
- full_cash: `4`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `7`
- research_watch: `151`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19200`
- MARKET_INELIGIBLE_SINGLETON: `6429`
- UNSAFE_OR_UNVERIFIED_LOCATION: `348`
- HIGHSEC_RESTRICTED_CAPITAL: `75`
- FATAL_OR_ACCESS_UNVERIFIED: `20`
- SKIN_DOMINANT: `7`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_DATA_INCOMPLETE: `7`
- LIST_TOO_SLOW: `5`
