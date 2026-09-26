# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-26T16:01:12.985Z`
- Market snapshot: `2026-09-26T15:48:34.336Z`
- Live pool: `160`; feasible: `94`
- CASH_FLOOR: `0`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
