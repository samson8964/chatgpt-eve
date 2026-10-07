# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-10-07T00:31:19.975Z`
- Market snapshot: `2026-10-07T00:18:26.043Z`
- Live pool: `117`; feasible: `70`
- CASH_FLOOR: `3`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
