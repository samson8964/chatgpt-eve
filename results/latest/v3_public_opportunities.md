# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-21T22:31:15.587Z`
- Market snapshot: `2026-09-21T22:48:36.797Z`
- Live pool: `168`; feasible: `110`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `1`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
