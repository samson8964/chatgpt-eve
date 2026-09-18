# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-18T16:31:25.212Z`
- Market snapshot: `2026-09-18T16:18:33.057Z`
- Live pool: `133`; feasible: `85`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
