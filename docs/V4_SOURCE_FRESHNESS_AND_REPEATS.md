# V4 historical source freshness and repeated opportunities (2026-10-15)

## Actual retrieval cadence

- `v4.full_scan` uses `v4.sources.advertised()` for EVE Ref's
  `market-orders/index.json` and `public-contracts/index.json`.
  It requires `last_modified` no older than **2 hours** for market
  orders and **3 hours** for public contracts, and downloads the advertised
  files into a new per-run private data directory. No previous-run cache
  is read by this code.
- EVE Ref documentation says regional market full snapshots run
  twice hourly (minute 15 and 45), while public contracts run twice
  hourly (minute 0 and 30). These are scheduled scrapes, not a
  guarantee that every order or contract changes each scrape.
- `v4.deep_scan` fetches 4-H, C-J and O4T structure market orders
  separately via our authorized Cloudflare endpoint,
  `GET /api/structure-market`, with full pagination. That Worker
  fetches authenticated EVE ESI `/markets/structures/{id}/` per page.
  The underlying API response may be cached for up to 300 seconds;
  a fresh HTTP request alone does not prove a different response.
- The Windows `EVE-V4-Shadow` task runs every 2 hours. A recurring
  source candidate can survive for days in game. Snapshot profitability
  is NOT live-verified, and some apparent C-J-to-Jita opportunity
  may be costly or inaccessible to haul.

## User-observed repeated notifications

The connected mailbox shows:
- 2026-10-14 20:44 Beijing, C-J type 41058: 13 units, net 1.11亿;
  type 1969: 861 units, net 0.79亿
- 2026-10-15 04:23 Beijing, type 41058: 13 units, net 1.33亿;
  type 1969: 818 units, net 0.73亿
- 2026-10-15 08:23 and 10:23 Beijing: same 2 market entries with
  identical displayed 8/818 units and 0.86/0.78亿 estimated net
  and the same top five contract entries/figures.

Therefore some snapshot-derived estimates DID change during the last
day, but identical displayed entries in the last two digests do NOT
prove identical source files. Existing game/Gmail mail receipts are
keyed to `run_name`; there is no cross-run candidate deduplication.

## Read-only historical audit

New `v4.freshness_audit` checks each completed run's archived
`full_market_report.json`, `deep_shadow.json` and
`all_proofs.jsonl` and reports:
- source `last_modified`, age *at scan*, and whether downloaded
  compressed public market/contract file SHA-256 changed since prior run
- each private market's order-row totals, plus (for newly generated
  runs) per-station book-fingerprint changes
- number of retained/new/vanished snapshot *model candidate keys* and
  retained profit changes; proof counts, without claiming live trades

It is non-networked, read-only and does not read Windows Credentials,
send mail, edit scan results or change Task Scheduler.

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
& .\.venv\Scripts\python.exe -m v4.freshness_audit --last 12
```

**Caveats:** Source SHA difference only proves bytes changed (metadata
or another region may have changed), not that a named item's price
changed. Two equal SHA hashes prove the entire archived compressed
file stayed byte-for-byte unchanged. Historical private structure
order books were not persisted or fingerprinted before this update;
they cannot be reconstructed from count-only health reports.
`v4.deep_scan` now archives SHA-256 fingerprints of complete active
order books for 4-H/C-J/O4T **without archiving private order details**.
After two new completed scans, the audit can say whether the complete
available active order books differ between scans.

**Recommendation (not enabled automatically):** preserve the full
two-hour census, but email new candidates or materially changed
executable depths/prices instead of every previously seen candidate
each run; keep a daily aggregate digest of persistent unchanged
opportunities. This requires a separate, explicit deduplication
policy and must not hide improved or expired opportunities.
