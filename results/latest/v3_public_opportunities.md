# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T23:01:46.590Z
- Market snapshot: 2026-10-09T22:48:31.641Z
- Candidate universe: 24619; deep validation pool: 252; feasible: 187
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 6
- RESEARCH: 164
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

- raw_contracts: `50319`
- eligible_contracts: `43663`
- market_executable_contracts: `24619`
- snapshot_candidates: `24619`
- candidate_pool: `610`
- location_executable: `252`
- feasible: `187`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `6`
- research_watch: `164`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18832`
- MARKET_INELIGIBLE_SINGLETON: `6199`
- UNSAFE_OR_UNVERIFIED_LOCATION: `358`
- HIGHSEC_RESTRICTED_CAPITAL: `59`
- BARTER_PROCUREMENT_INCOMPLETE: `10`
- SKIN_DOMINANT: `6`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `4`
- LIST_DATA_INCOMPLETE: `4`
