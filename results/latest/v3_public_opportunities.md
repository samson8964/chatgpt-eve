# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T14:31:42.766Z
- Market snapshot: 2026-10-10T14:48:44.404Z
- Candidate universe: 24640; deep validation pool: 275; feasible: 197
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 9
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

- raw_contracts: `50318`
- eligible_contracts: `43755`
- market_executable_contracts: `24640`
- snapshot_candidates: `24640`
- candidate_pool: `610`
- location_executable: `275`
- feasible: `197`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `9`
- research_watch: `159`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18893`
- MARKET_INELIGIBLE_SINGLETON: `6270`
- UNSAFE_OR_UNVERIFIED_LOCATION: `335`
- HIGHSEC_RESTRICTED_CAPITAL: `74`
- BARTER_PROCUREMENT_INCOMPLETE: `8`
- LIST_TOO_SLOW: `5`
- SKIN_DOMINANT: `4`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
