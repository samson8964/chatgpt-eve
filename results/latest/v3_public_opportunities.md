# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-29T12:01:14.074Z`
- Market snapshot: `2026-09-29T11:48:59.700Z`
- Live pool: `138`; feasible: `85`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
