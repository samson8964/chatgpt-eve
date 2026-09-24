# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-24T12:01:13.390Z`
- Market snapshot: `2026-09-24T12:18:38.543Z`
- Live pool: `173`; feasible: `110`
- CASH_FLOOR: `0`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
