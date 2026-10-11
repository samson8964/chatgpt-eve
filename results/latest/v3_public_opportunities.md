# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-11T21:31:42.374Z
- Market snapshot: 2026-10-11T21:48:41.030Z
- Candidate universe: 24933; deep validation pool: 245; feasible: 164
- FULL_CASH: 2
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

- raw_contracts: `50868`
- eligible_contracts: `44195`
- market_executable_contracts: `24933`
- snapshot_candidates: `24933`
- candidate_pool: `611`
- location_executable: `245`
- feasible: `164`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `4`
- research_watch: `158`
- mail_eligible: `1`

## Rejection reasons

- BPC_ROUTED: `19028`
- MARKET_INELIGIBLE_SINGLETON: `6459`
- UNSAFE_OR_UNVERIFIED_LOCATION: `366`
- HIGHSEC_RESTRICTED_CAPITAL: `75`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- LIST_DATA_INCOMPLETE: `7`
- SKIN_DOMINANT: `6`
- LIST_TOO_SLOW: `6`
