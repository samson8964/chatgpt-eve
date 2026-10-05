# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-10-05T03:31:16.544Z`
- Market snapshot: `2026-10-05T03:18:22.171Z`
- Live pool: `113`; feasible: `65`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
