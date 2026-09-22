# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-22T04:01:16.373Z`
- Market snapshot: `2026-09-22T04:18:29.004Z`
- Live pool: `164`; feasible: `105`
- CASH_FLOOR: `0`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
