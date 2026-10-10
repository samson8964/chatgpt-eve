# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-10T07:02:48.796Z
- Market snapshot: 2026-10-10T06:48:55.401Z
- Candidate universe: 24763; deep validation pool: 268; feasible: 193
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 10
- RESEARCH: 157
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

- raw_contracts: `50428`
- eligible_contracts: `43830`
- market_executable_contracts: `24763`
- snapshot_candidates: `24763`
- candidate_pool: `610`
- location_executable: `268`
- feasible: `193`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `10`
- research_watch: `157`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18849`
- MARKET_INELIGIBLE_SINGLETON: `6291`
- UNSAFE_OR_UNVERIFIED_LOCATION: `342`
- HIGHSEC_RESTRICTED_CAPITAL: `71`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `4`
- FATAL_OR_ACCESS_UNVERIFIED: `4`
- LIST_TOO_SLOW: `2`
