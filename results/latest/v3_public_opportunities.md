# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-10-04T13:31:19.829Z`
- Market snapshot: `2026-10-04T13:18:26.251Z`
- Live pool: `114`; feasible: `62`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
