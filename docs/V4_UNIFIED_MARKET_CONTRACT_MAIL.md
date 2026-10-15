## 2026-10-14: 4-H and O4T market coverage + five quote-level averages

**User question:** how many item types were scanned at 4-H and O4T in
the previous scan, were all compared with Jita bids, and show the
source first-five sell group average and Jita first-five buy group average
for each market opportunity in future emails.

### Precise historical limitations

Previous deep reports include `structure_health.four_h.orders` and
`structure_health.o4t.orders`. These are **numbers of orders**, not
unique item types and not necessarily just sell orders. The old program
did not persist each structure's full type universe or distinct source
sell-type count. Existing `all_proofs.jsonl` only contains
optimistic-profit-qualified market pairs; do NOT infer the count of all
scanned item types from it or from how many entries appeared in an email.

Use a read-only, no-network local command against the most recently
completed V4 scan:

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
& .\.venv\Scripts\python.exe -m v4.market_station_audit
```

It reports **4-H, C-J and O4T** source order totals,
eligible full-depth-pair counts and model-candidate counts, with unknown
historical distinct item counts as `null`; it will not fake missing data.
After a **new** scan produced by the updated engine it also reports:
- `active_sell_type_ids` (distinct commodity type IDs among valid
  active structure SELL orders); `active_sell_orders`
- `sell_types_with_jita_buy`, `sell_types_without_jita_buy`
- `sell_types_best_price_crossed` (source lowest ask < Jita highest bid)
- `sell_types_optimistic_gate_passed` (gross theoretical spread upper
  bound >= 50m ISK) and actual `full_depth_market_pairs_evaluated`.
Every valid source sell type is checked for **existence of Jita buy
orders and its best buy price**, whether or not it survives the optimistic
profit filter. Only potentially profitable types undergo full matched
bid/ask depth + shipping/tax/ROI/stress calculations, for efficiency.
A missing Jita buy order is not silently counted as a zero-value trade.

### Future market emails: exact price semantics

For a market lead, `v4/deep_scan.py` now records on the opportunity proof:
- `source_top5_sell`: **five lowest distinct sell PRICE LEVELS** at
  the source station, each price in ISK per unit; orders at identical
  prices share one level, no volume weighting.
- `jita_top5_buy`: **five highest distinct buy PRICE LEVELS** at
  Jita station ID `60003760`, also unweighted.
- `simple_mean_isk_per_unit` = arithmetic average of the **actual
  available up to five levels**, with `group_count` explicit.
If a book has only 1-4 levels, the email says `卖3档均` for 3, for
example; never invents unavailable quotes. This is **descriptive quote
context**, not a substitute for full depth, execution volume or net
profit. Very cheap per-unit items use 万/ISK to avoid displaying
meaningless 0.00亿.

Short per-market entry now contains
`[clickable item] ×quantity location 净X.XX亿 ROI… | 卖N档均… / 吉买N档均…`.
Gmail and EVE game mail share the same figures but use their own
clickable link formats. Each email still shows a maximum of five
market items and five contract leads, does not turn shadow research
into actionable live-trade alerts and does not add a scheduled task.

After the update, complete **one fresh full scan**. Older saved market
proofs cannot backfill these quote-level means because the underlying
private order books were not persisted.

## 2026-10-14 shorter clickable messages

The user confirmed prior deliveries were too verbose and links were not
usable. V4 now treats the **target itself as the clickable title**, with
no separate long instruction paragraphs.

- Game mail: native EVE HTML
  `<url=contract:0//ID><b>打开合同 ID</b></url>` and
  `<url=showinfo:TYPEID><b>查看商品 TYPEID</b></url>`.
  The latter opens item Show Info; it is **not** a promise to open or
  purchase a particular market order. The link should be tested in
  the recipient's running EVE client. The Worker passes body markup
  unchanged to ESI.
- Gmail: **multipart plain + HTML**, with clickable anchor text
  `打开合同 ID` pointing to Worker `/c/ID` and
  `查看商品 TYPEID` pointing to Worker `/m/TYPEID`. Clicking a
  Worker link may require the game's authorized character to be online
  to display the target window.
- Per result: clickable target + pickup location + quantity (market) or
  contract price + estimated net profit + ROI. At most five of each
  lane, one short risk warning, nothing about SQLite proof counts,
  catalog metadata, research process or lengthy disclaimers.
- Prices remain at 0.01 亿 ISK precision.
- The prior successful contract emails and dedupe receipts are not
  retroactively edited or replayed. A *new* successful scan after
  Windows `git pull --ff-only` is required to receive the new format.
- Automated tests confirm exact EVE markup and true Gmail HTML
  anchors; rendering inside the customer's EVE client cannot be
  verified by GitHub Actions, so require one human click test after
  mail arrival.

# V4: Combined market and contract reports (2026-10-14)

**Accepted requirement:** one existing two-hour Windows shadow scan covers both
market and public contract evidence; each enabled mail channel gets **one**
compact combined report per completed run, no new job, no old V3.

## Corrected pricing and risk

- Market sources: approved Jita-external stations and 4-H/C-J/O4T markets
  whose source order books are available. Market exit is only **Jita 4-4
  station 60003760 BUY depth**; no Amarr/structure local bid assumed
  as Jita value. Jita itself is already the destination, not the source
  for cross-region arbitrage.
- Contract items: all located at approved source locations, valued against
  Jita 4-4 BUY depth only; a contract's pickup site affects access and haul.
- Critical safety fix: market shipping estimate now uses **full executable
  matched quantity x per-item volume**, instead of charging haul for one
  item even when 100 or 10,000 are bought. Bid/ask matched depth and
  best-order removal stress test remain required; estimates are not
  live verified, and capital, margins, access and routes need validation.
- Market and contract proofs remain separately stored as market and contract
  entries in each run's `all_proofs.jsonl`. The combined digest is built from
  the same run's deep report and complete evidence; it verifies
  `market_proofs_examined`, Jita pricing metadata and
  `SHADOW_ONLY_NO_LIVE_ALERTS` before displaying candidates.

## Very short delivery

New formatter `v4/unified_review.py` emits up to five prioritized market
and five contract snapshot candidates, with:
- **Amount precision**: ISK / 100,000,000, always **0.01亿** such as
  `0.59亿`, `1.23亿`. Net, purchase price and stress all use the same
  convention.
- Profit, ROI, optional stressed profit, location, item type ID/quantity or
  contract ID. Short header with market audited and contract audited counts.
- **Game mail contract link**: native supported EVE rich text
  `<url=contract:0//236977688><b>打开合同</b></url>`.
  This is the game-client clickable format already used by former mail code,
  not a plain HTTP URL that EVE may fail to linkify.
- **Game mail market link**:
  `<url=showinfo:34><b>查看物品</b></url>`; source and Jita-4-4
  destination are visible.
- **Gmail links**: exact HTTP contract
  `https://eve-contract-opener.99617224.workers.dev/c/<id>` and item
  `https://eve-contract-opener.99617224.workers.dev/m/<typeid>`.
  These URLs use already deployed Worker routes.
- Explicit one-line `快照候选 ... 不可直接购买` at end.
  Nothing in the combined report is a confirmed live order/contract.

Both `v4.research_mail.send_review` and
`v4.game_mail_review.send_review_to_game` now import
`v4.unified_review.make_review`; they each render channel-appropriate
links. Existing Gmail and in-game mail configurations and per-run dedupe
receipts remain intact. The next successful post-update run produces the
new combined message. Old per-run receipts are not deleted or resent.
If a scan is incomplete, the candidate lists are blank and the mail
reports incomplete source status.

## Desktop monitor

Read-only `desktop_status` now shows market and contract examined counts
from the most recent fully recorded deep report and the *research* Gmail
and EVE opt-in flags from local nonsecret config files. The floating
widget no longer falsely says `MAIL OFF` after enabling the two review
channels. Formal production alerts remain off.

## Windows local rollout

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
Get-ScheduledTask -TaskName 'EVE-V4-Shadow'
```

The existing Windows scheduled scan continues every two hours and triggers
both already enabled mail channels at the end of each completed run.
No credential re-entry or new Task Scheduler task is required. To manually
check/trigger one new scan:

```powershell
$task = Get-ScheduledTask -TaskName 'EVE-V4-Shadow'
if ($task.State -ne 'Running') {
    Start-ScheduledTask -TaskName 'EVE-V4-Shadow'
}
```

Check `EVE-V4-Data/logs/shadow-task.log` for the newest
`RESULT`, `REVIEW_MAIL`, `GAME_REVIEW_MAIL` and exact run folder.
Verify actual inbox delivery before calling it fully deployed.
All mail failures are logged separately. No new mail until local
Windows pulls this commit and completes another scan.

## Current evidence / limitations

The existing connected Gmail mailbox received one V4 contract-only summary
dated **2026-10-14 19:37 Beijing**. It reported **36,239 contract proofs
examined, 37,563 total SQLite proofs and 38 contract research leads**.
It did *not* report a verified market opportunity count; market proof
auditing was known to exist in code but market push was missing. Market
candidate counts will only be verifiable from a new post-update scan.
GitHub CI only tests code; it cannot prove a Windows task has fetched
the new branch or successfully pushed actual opportunities.

## 2026-10-14: approved direct replacement — matched depth, lot optimization and VWAP

User explicitly approved replacing the old screening/display rules **without a
parallel A/B experiment**. This does not waive normal CI or local acceptance.
No official LIVE trading alerts are enabled by this change.

1. **Coverage remains full.** Every active sell `type_id` in each authorized
   structure is compared with the existence and best station-specific BUY order
   at Jita IV-4, ID `60003760`. No TOP-N truncation and no historical
   seen-key filter before screening.
2. **Optimistic prefilter now considers BOTH sides' depth.** For each
   positively crossed station/type pair, align local asks low-to-high with
   Jita station bids high-to-low and accumulate
   `matched_units * (Jita_bid - source_ask)` until no positive spread.
   This fee-free gross bound is safe for excluding pairs below 50,000,000 ISK:
   tax, freight, order limits and access can only reduce realized profit.
   Existing census key `sell_types_optimistic_gate_passed` now counts
   THIS depth-aware ceiling, not best-price * all local sell volume.
   Full fee/ROI/haul/stress calculation remains downstream.
3. **Quantity/lot selection.** The deep engine checks profitable order
   boundaries, loss-of-best-Jita-BUY boundaries, minimum fills, and integer
   neighbours near economic gate crossings. It separately prices transport
   on the selected total lot's physical volume and requires an alternate
   buy-side-only stress fill for the SAME lot quantity. Normal lots must pass
   `50m ISK / ROI >=10% / density >=2000 ISK/m3`, and stressed net
   must strictly exceed `50m ISK` after the best Jita BUY order disappears.
   it chooses highest net profit, not maximum mechanically crossed volume.
   Unevaluated or unsupported minimum-volume cases fail closed.
4. **Matched VWAPs.** Each market proof stores
   `source_vwap_isk_per_unit = executed_sell_cost / selected_quantity`
   and `jita_vwap_isk_per_unit = executed_jita_buy_gross / selected_quantity`.
   These are *hypothetical snapshot depth execution prices*, not completed
   trades. Both prices use exactly the same selected quantity. The combined
   email displays these primarily and preserves source/Jita distinct-price
   first-five simple averages only as clearly-labelled contextual quotes.
   Old snapshots without explicit depth/VWAP proofs are not remailed.
5. **No A/B rollout.** On the Windows host, update the existing
   `prep/v4-windows-local-migration-20261013` branch, use the existing
   scheduled `EVE-V4-Shadow` job for ONE new scan, then confirm the new
   report contains `market_execution_basis=OPTIMIZED_MATCHED_QUANTITY_AND_VWAP`.
   The local machine must independently pull this commit; a passing GitHub
   Action does not update or start a Windows scheduled task.
   The only outbound mail remains clearly marked `V4捡漏待核`.

## 2026-10-15: approved asymmetric market stress and stricter exit floor

The source's cheapest sell order is the opportunity being purchased, NOT an
inventory-risk stress input. Preserve ALL actual source asks, including a single
discounted order, during quantity generation and the stress calculation.
Before any future LIVE purchase, recheck source ask ID, price, available
quantity/minimum fill and station access; if the target ask vanished, do not buy.

For the stress scenario, drop **only the highest-priced Jita IV-4 BUY order**
and require the remaining buy order book to execute **the same selected lot**
after tax and full-lot estimated hauling with net profit **strictly greater than
50,000,000 ISK**. Normal profit floor, ROI>=10%, and density>=2,000 ISK/m3
stay unchanged. A 50,000,000 ISK stressed net is NOT sufficient.
No substitution of fewer units for the same-lot stress test.

Fix companion latent omission: when there is only ONE valid candidate-quantity
breakpoint, always evaluate it; the old adjacent-pairs-only loop silently
discarded that candidate. Retain the prior actual-book-depth optimistic
prefilter and no TOP-N or historical-seen truncation.

Update both `v4/engine.py` and `v4/market_execution.py`, plus
`v4/unified_review.py` to fail closed on any legacy/replayed model candidate
with stressed profit <=50m ISK. This is still SHADOW research, never a claim of
a live executable deal. Local Windows activation requires branch pull and a
fresh observed scan; GitHub CI alone cannot deploy Windows code.
