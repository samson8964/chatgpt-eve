# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-21T04:31:12.898Z`
- Market snapshot: `2026-09-21T04:48:27.363Z`
- Live pool: `151`; feasible: `89`
- CASH_FLOOR: `0`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
