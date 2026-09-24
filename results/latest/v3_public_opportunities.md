# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-24T01:31:14.097Z`
- Market snapshot: `2026-09-24T01:48:29.556Z`
- Live pool: `162`; feasible: `104`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
