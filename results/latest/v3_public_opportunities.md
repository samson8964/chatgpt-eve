# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-10-06T15:31:22.784Z`
- Market snapshot: `2026-10-06T15:18:21.698Z`
- Live pool: `124`; feasible: `77`
- CASH_FLOOR: `3`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
