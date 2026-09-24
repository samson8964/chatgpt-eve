# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-24T01:01:12.299Z`
- Market snapshot: `2026-09-24T00:48:43.151Z`
- Live pool: `169`; feasible: `110`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
