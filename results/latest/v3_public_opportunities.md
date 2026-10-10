# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T13:01:36.920Z
- Market snapshot: 2026-10-10T12:48:47.133Z
- Candidate universe: 24676; deep validation pool: 258; feasible: 184
- FULL_CASH: 0
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 11
- RESEARCH: 155
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

- raw_contracts: `50360`
- eligible_contracts: `43751`
- market_executable_contracts: `24676`
- snapshot_candidates: `24676`
- candidate_pool: `610`
- location_executable: `258`
- feasible: `184`
- full_cash: `0`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `11`
- research_watch: `155`
- mail_eligible: `0`

## Rejection reasons

- BPC_ROUTED: `18854`
- MARKET_INELIGIBLE_SINGLETON: `6259`
- UNSAFE_OR_UNVERIFIED_LOCATION: `352`
- HIGHSEC_RESTRICTED_CAPITAL: `68`
- FATAL_OR_ACCESS_UNVERIFIED: `7`
- SKIN_DOMINANT: `6`
- BARTER_PROCUREMENT_INCOMPLETE: `6`
- LIST_TOO_SLOW: `4`
