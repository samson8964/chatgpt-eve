# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-29T09:31:15.947Z`
- Market snapshot: `2026-09-29T09:48:43.636Z`
- Live pool: `142`; feasible: `76`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
