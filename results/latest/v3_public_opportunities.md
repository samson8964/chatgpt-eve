# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-24T10:31:15.343Z`
- Market snapshot: `2026-09-24T10:48:35.329Z`
- Live pool: `162`; feasible: `100`
- CASH_FLOOR: `0`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
