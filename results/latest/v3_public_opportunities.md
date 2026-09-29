# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-29T16:31:16.161Z`
- Market snapshot: `2026-09-29T16:18:39.692Z`
- Live pool: `133`; feasible: `77`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
