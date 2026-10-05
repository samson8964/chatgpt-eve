# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-10-05T19:01:52.673Z`
- Market snapshot: `2026-10-05T18:48:51.888Z`
- Live pool: `115`; feasible: `69`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
