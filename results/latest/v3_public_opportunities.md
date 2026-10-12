# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T08:31:39.924Z
- Market snapshot: 2026-10-12T08:18:31.797Z
- Candidate universe: 25034; deep validation pool: 245; feasible: 171
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 158
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

- raw_contracts: `50840`
- eligible_contracts: `44333`
- market_executable_contracts: `25034`
- snapshot_candidates: `25034`
- candidate_pool: `611`
- location_executable: `245`
- feasible: `171`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `158`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19068`
- MARKET_INELIGIBLE_SINGLETON: `6489`
- UNSAFE_OR_UNVERIFIED_LOCATION: `366`
- HIGHSEC_RESTRICTED_CAPITAL: `69`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_TOO_SLOW: `6`
- LIST_DATA_INCOMPLETE: `6`
- SKIN_DOMINANT: `5`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
