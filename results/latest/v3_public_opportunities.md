# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-24T23:31:13.587Z`
- Market snapshot: `2026-09-24T23:48:32.926Z`
- Live pool: `159`; feasible: `98`
- CASH_FLOOR: `0`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
