# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-10-03T17:31:19.554Z`
- Market snapshot: `2026-10-03T17:48:25.140Z`
- Live pool: `117`; feasible: `65`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `1`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
