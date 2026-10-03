# Freelance Jobs Arbitrage Radar v1

## Goal
Find executable player-created Freelance Jobs where the payout exceeds the real acquisition and delivery cost by a meaningful margin. Discovery is not an opportunity until item identity, destination, cost, capacity, expiry and route risk are verified.

## Pipeline
1. **Snapshot** — fetch the complete public no-ACL Freelance Jobs pool; preserve raw JSON and timestamp.
2. **Cheap gate** — Active only; not expired; supported method first = DeliverItem; remaining contribution > 0; reward > 0.
3. **Decode** — fetch job detail; resolve item type IDs, station/structure IDs, corporation, broadcast systems, contribution limits and expiry.
4. **Acquisition pricing** — obtain Jita 4-4 executable ask depth for the exact quantity required. Do not use a single best price when quantity > 1. Record VWAP and total acquisition cost.
5. **Delivery feasibility** — resolve delivery destination. NPC station can be route-priced automatically. Unresolvable/private Upwell structures are HOLD, not opportunities.
6. **Economics** — gross payout = reward_per_contribution * feasible contributions. Net = gross payout - executable acquisition cost - estimated hauling cost - explicit fees. ROI = net/acquisition cost. Keep transport risk separate from accounting cost.
7. **Risk gate** — route jumps, low/null-sec exposure, cargo value, expiry buffer, participant/contribution caps, and stale-job risk. Never assume broadcast location equals delivery location.
8. **Opportunity gate** — only surface when item identity + executable market cost + delivery destination + remaining capacity are verified. Otherwise label RESEARCH/HOLD with reason.
9. **Output** — Top opportunities plus denominator: jobs scanned, DeliverItem count, decoded count, market-priced count, destination-resolved count, opportunity count, rejection reasons.

## First-test thresholds
These are test thresholds, not permanent policy:
- Net profit >= 50m ISK
- ROI >= 10%
- expiry buffer >= 6h
- acquisition quantity fully fillable from executable Jita sell orders
- NPC-station delivery preferred for v1
- Upwell/private structure => HOLD until accessibility is verified

## Ranking
Rank only verified opportunities:
1. net profit
2. ROI
3. net profit per jump
4. expiry buffer / operational risk

Do not rank raw reward as profit.

## Regression candidates
- Thunderchild Blueprint — job a1e620e1-14af-421c-9a05-aae959efdddf; DeliverItem type 54844; 350m/contribution.
- Omnia Guild Manufacturing Division — f11d4ff7-8204-41f1-97c8-e4085032c819; DeliverItem type 641; 180m/contribution; participant limit 1.
- WTB SP LP — e9a15a5c-7e0f-4c4f-b879-ddb940cfef6a; DeliverItem type 93611; 76.5m/contribution; broadcast Onnamon/Intaki.
- T3-Forschung Intact Hull Section — e62ead68-65af-403e-9963-e98916b8f1ad; DeliverItem type 30752; 72.36634m/contribution; structure destinations; expected HOLD until access/destination is verified.

## Safety
Read-only discovery and analysis only. Never accept a job, buy an item, move assets, or spend ISK automatically.
