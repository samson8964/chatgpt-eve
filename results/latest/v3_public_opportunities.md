# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-28T11:31:24.703Z`
- Market snapshot: `2026-09-28T11:48:42.473Z`
- Live pool: `146`; feasible: `75`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
