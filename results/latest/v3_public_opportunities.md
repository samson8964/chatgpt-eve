# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-26T16:01:12.985Z`
- Market snapshot: `2026-09-26T16:18:36.464Z`
- Live pool: `151`; feasible: `85`
- CASH_FLOOR: `0`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
