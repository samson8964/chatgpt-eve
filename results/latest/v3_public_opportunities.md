# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-19T09:31:18.042Z`
- Market snapshot: `2026-09-19T09:48:38.773Z`
- Live pool: `122`; feasible: `76`
- CASH_FLOOR: `2`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
