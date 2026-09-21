# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-21T19:01:16.009Z`
- Market snapshot: `2026-09-21T19:18:37.487Z`
- Live pool: `155`; feasible: `97`
- CASH_FLOOR: `0`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
