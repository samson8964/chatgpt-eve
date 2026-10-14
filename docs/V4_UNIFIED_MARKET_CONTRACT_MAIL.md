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
