# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-09-25T09:01:12.054Z`
- Market snapshot: `2026-09-25T09:18:31.769Z`
- Live pool: `164`; feasible: `95`
- CASH_FLOOR: `0`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
