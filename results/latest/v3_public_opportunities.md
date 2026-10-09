# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T23:01:46.590Z
- Market snapshot: 2026-10-09T23:18:38.026Z
- Candidate universe: 24616; deep validation pool: 250; feasible: 183
- FULL_CASH: 5
- PARTIAL_CASH_FLOOR: 1
- BARTER: 0
- LIST-SUPPORTED: 15
- RESEARCH: 153
- FORMAL MAIL: 5

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
- eligible_contracts: `43662`
- market_executable_contracts: `24616`
- snapshot_candidates: `24616`
- candidate_pool: `610`
- location_executable: `250`
- feasible: `183`
- full_cash: `5`
- partial_cash_floor: `1`
- barter: `0`
- list_supported: `15`
- research_watch: `153`
- mail_eligible: `5`

## Rejection reasons

- BPC_ROUTED: `18832`
- MARKET_INELIGIBLE_SINGLETON: `6201`
- UNSAFE_OR_UNVERIFIED_LOCATION: `360`
- HIGHSEC_RESTRICTED_CAPITAL: `65`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- FATAL_OR_ACCESS_UNVERIFIED: `6`
- LIST_DATA_INCOMPLETE: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `2`
