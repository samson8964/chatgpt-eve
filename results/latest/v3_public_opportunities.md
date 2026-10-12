# Opportunity Engine V3 — redesigned architecture

- Contracts snapshot: 2026-10-12T12:01:39.303Z
- Market snapshot: 2026-10-12T11:48:39.519Z
- Candidate universe: 25079; deep validation pool: 271; feasible: 193
- FULL_CASH: 2
- PARTIAL_CASH_FLOOR: 0
- BARTER: 0
- LIST-SUPPORTED: 5
- RESEARCH: 162
- FORMAL MAIL: 2

Design rules:
- Broad discovery is separate from final purchase recommendation.
- Every deep candidate produces an ExecutionProof before policy classification.
- FULL_CASH -> PARTIAL_CASH_FLOOR -> LIST-SUPPORTED are mutually exclusive for pure item contracts.
- Listing valuation is WATCH-only and can never masquerade as locked cash.
- Formal mail still requires the production profit/ROI/profit-density gate.
- FULL_CASH mail is disabled by default while V2 remains the production fallback; set V3_FULL_CASH_MAIL_ENABLED=1 only at cutover.

# Rejection Funnel

## Stages

- raw_contracts: `50816`
- eligible_contracts: `44357`
- market_executable_contracts: `25079`
- snapshot_candidates: `25079`
- candidate_pool: `611`
- location_executable: `271`
- feasible: `193`
- full_cash: `2`
- partial_cash_floor: `0`
- barter: `0`
- list_supported: `5`
- research_watch: `162`
- mail_eligible: `2`

## Rejection reasons

- BPC_ROUTED: `19049`
- MARKET_INELIGIBLE_SINGLETON: `6507`
- UNSAFE_OR_UNVERIFIED_LOCATION: `340`
- HIGHSEC_RESTRICTED_CAPITAL: `72`
- FATAL_OR_ACCESS_UNVERIFIED: `10`
- BARTER_PROCUREMENT_INCOMPLETE: `7`
- SKIN_DOMINANT: `6`
- LIST_TOO_SLOW: `4`
