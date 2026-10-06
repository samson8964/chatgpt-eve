# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-10-06T22:01:20.547Z`
- Market snapshot: `2026-10-06T21:48:24.468Z`
- Live pool: `118`; feasible: `74`
- CASH_FLOOR: `3`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
