# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-18T19:01:15.288Z`
- Market snapshot: `2026-09-18T19:18:26.690Z`
- Live pool: `134`; feasible: `87`
- CASH_FLOOR: `2`
- BARTER: `0`
- CONSERVATIVE_LIST: `1`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
