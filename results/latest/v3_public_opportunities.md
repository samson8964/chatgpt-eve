# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T15:01:43.901Z
- Market snapshot: 2026-10-10T15:18:46.702Z
- Candidate universe: 24624; deep validation pool: 259; feasible: 186
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 162
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

- raw_contracts: `50394`
- eligible_contracts: `43742`
- market_executable_contracts: `24624`
- snapshot_candidates: `24624`
- candidate_pool: `610`
- location_executable: `259`
- feasible: `186`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `162`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18893`
- MARKET_INELIGIBLE_SINGLETON: `6290`
- UNSAFE_OR_UNVERIFIED_LOCATION: `351`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- FATAL_OR_ACCESS_UNVERIFIED: `5`
- LIST_TOO_SLOW: `4`
- SKIN_DOMINANT: `2`
