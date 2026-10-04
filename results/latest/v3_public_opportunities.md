# Opportunity Engine V3 — missed-opportunity channels

- Contracts snapshot: `2026-10-04T06:01:16.984Z`
- Market snapshot: `2026-10-04T06:18:24.045Z`
- Live pool: `115`; feasible: `60`
- CASH_FLOOR: `0`
- BARTER: `0`
- CONSERVATIVE_LIST: `0`

V3 is additive. Existing V2 SAFE channels are unchanged.
Cash-floor leftovers are explicitly valued at zero.
Barter requires complete live Jita procurement depth for all requested inputs.
Conservative-list requires current asks, historical turnover, haircut pricing and <= configured fill-days.
