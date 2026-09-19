# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-19T14:01:22.344Z`
- Market snapshot: `2026-09-19T14:18:39.981Z`
- Live pool: `132`; feasible: `86`
- CASH_FLOOR: `1`
- BARTER: `0`
- CONSERVATIVE_LIST: `1`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
