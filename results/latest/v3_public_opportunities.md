# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-23T22:31:14.248Z`
- Market snapshot: `2026-09-23T22:48:34.885Z`
- Live pool: `153`; feasible: `93`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
