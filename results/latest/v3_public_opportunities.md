# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-24T04:31:14.109Z`
- Market snapshot: `2026-09-24T04:48:36.942Z`
- Live pool: `157`; feasible: `97`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
