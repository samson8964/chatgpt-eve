# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-24T08:01:15.002Z`
- Market snapshot: `2026-09-24T07:48:33.668Z`
- Live pool: `163`; feasible: `100`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
