# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-22T09:31:15.821Z`
- Market snapshot: `2026-09-22T09:48:35.205Z`
- Live pool: `161`; feasible: `104`
- CASH_FLOOR: `0`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
