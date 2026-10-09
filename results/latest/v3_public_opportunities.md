# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-09T01:02:40.495Z
- Market snapshot: 2026-10-09T01:18:21.261Z
- Candidate universe: 24309; deep validation pool: 243; feasible: 171
- FULL_CASH: 1
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 4
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

- raw_contracts: `50092`
- eligible_contracts: `43393`
- market_executable_contracts: `24309`
- snapshot_candidates: `24309`
- candidate_pool: `607`
- location_executable: `243`
- feasible: `171`
- full_cash: `1`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `158`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `18861`
- MARKET_INELIGIBLE_SINGLETON: `6011`
- UNSAFE_OR_UNVERIFIED_LOCATION: `364`
- HIGHSEC_RESTRICTED_CAPITAL: `67`
- FATAL_OR_ACCESS_UNVERIFIED: `8`
- SKIN_DOMINANT: `5`
- LIST_DATA_INCOMPLETE: `5`
- LIST_TOO_SLOW: `3`
- BARTER_PROCUREMENT_INCOMPLETE: `2`
