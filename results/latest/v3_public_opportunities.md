# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-23T10:01:15.648Z`
- Market snapshot: `2026-09-23T10:18:38.559Z`
- Live pool: `163`; feasible: `106`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
