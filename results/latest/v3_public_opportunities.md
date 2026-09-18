# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-18T18:01:15.299Z`
- Market snapshot: `2026-09-18T18:18:34.444Z`
- Live pool: `135`; feasible: `88`
- CASH_FLOOR: `2`
- BARTER: `0`
- CONSERVATIVE_LIST: `1`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
