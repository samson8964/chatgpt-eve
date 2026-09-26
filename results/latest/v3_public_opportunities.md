# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-26T19:31:18.284Z`
- Market snapshot: `2026-09-26T19:48:34.956Z`
- Live pool: `165`; feasible: `94`
- CASH_FLOOR: `0`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
