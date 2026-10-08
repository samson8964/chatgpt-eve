# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-08T00:01:46.161Z
- Market snapshot: 2026-10-08T00:18:20.760Z
- Candidate universe: 24551; deep validation pool: 231; feasible: 164
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
- RESEARCH: 149
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

- raw_contracts: `49959`
- eligible_contracts: `43394`
- market_executable_contracts: `24551`
- snapshot_candidates: `24551`
- candidate_pool: `605`
- location_executable: `231`
- feasible: `164`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `149`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18620`
- MARKET_INELIGIBLE_SINGLETON: `6000`
- UNSAFE_OR_UNVERIFIED_LOCATION: `374`
- HIGHSEC_RESTRICTED_CAPITAL: `64`
- FATAL_OR_ACCESS_UNVERIFIED: `9`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
- SKIN_DOMINANT: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
