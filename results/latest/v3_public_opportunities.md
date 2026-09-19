# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-19T14:31:16.565Z`
- Market snapshot: `2026-09-19T14:48:36.800Z`
- Live pool: `130`; feasible: `84`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `1`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
