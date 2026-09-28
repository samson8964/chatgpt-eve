# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-28T02:31:14.979Z`
- Market snapshot: `2026-09-28T02:48:40.151Z`
- Live pool: `145`; feasible: `72`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
