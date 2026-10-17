# V4 Official ESI one-shot public-market comparison

**Independent shadow evaluation only. No modification to V4 production data source, scheduled tasks, contracts, private structure markets, profit rules or mail.**

## Scope

Discover all region IDs through public ESI /universe/regions/ and read EVERY /markets/{region_id}/orders/ page via X-Pages. Require nonempty pages, a constant X-Pages count, consistent Last-Modified across the region, validated order rows and no duplicate order IDs.

HTTP 404 is explicitly MARKET_ENDPOINT_404_UNVERIFIED, never silently considered zero market orders. These regions are compared against the local EVE Ref baseline; if a known market region becomes 404, coverage is flagged unverified. The public API normally omits Upwell structure orders. The existing authorized 4-H, C-J and O4T scans are unchanged. No SSO is needed for public-region orders.

Obey 5-minute ESI caching and CCP rate limits: 3 threads default, globally paced requests at >=0.2s spacing, 429 Retry-After and bounded retry. No unbounded pagination and no auto-scheduling. Data from an inconsistent multi-page cache generation is rejected, not counted as complete.

## Run ONE full validation on the local Windows host

In a normal PowerShell window, outside the main V4 scheduled scan when possible:

    Set-Location (Join-Path $HOME 'EVE-V4-Code')
    git pull --ff-only
    & .\.venv\Scripts\python.exe -m unittest v4.tests.test_esi_parallel_validation -v
    & .\.venv\Scripts\python.exe -m v4.esi_parallel_validation --workers 3

Do not add --max-regions for the full test. For a quick smoke-test only, --max-regions 3 is available and is always marked PARTIAL_REGION_TEST_ONLY.

Results are written exclusively to EVE-V4-Data/esi-parallel-validation/<UTC-run-id>/:
- report.json: region results, every failure and 404, ESI page/unique order counts, cache ages and comparison
- comparison.sqlite3: independent ESI and archived EVE Ref order-ID rows, without changing the V4 ledger
- regions/<region_id>.jsonl.gz: independently completed region pages; no incomplete archives

If available, the reference is the latest successfully recorded V4 EVE Ref market-orders.csv.bz2. A stale reference is still valid for a historical difference comparison but NOT proof that ESI failed to find its orders.


## October 18 audit: reuse the 965,510 already archived ESI orders

The initial live run 20261017T213545Z-f56eeb8f queried all 114 regions,
received 1,307 HTTP-200 responses and archived 965,510 orders from 58
regions. It failed to produce the comparison due to the original validator:
54 regions had empty one-page markets, 2 major market regions had orders
rejected with generic INVALID_VALUE, and a historical EVE Ref reference
had non-actionable exhausted zero-remaining orders. **This is an incomplete
comparison, not proof that only 965,510 public market orders exist.**

After pulling the patch, reuse those 965,510 records without ANY new ESI
request. Only the independent forensic files reconciliation.json and
reconciled.sqlite3 are added; the previous report and previous SQLite
remain unmodified.

    & .\.venv\Scripts\python.exe -m v4.esi_parallel_validation --reconcile-run 20261017T213545Z-f56eeb8f

A no-reference-data or bad-input error is an explicit failure; never
relabel the original 58/114 coverage as complete.

Before running all regions again, separately inspect the two large trade
regions that previously failed (The Forge and Domain). The targeted run
downloads only the requested region IDs, is explicitly PARTIAL_REGION_TEST_ONLY,
and prints the exact rejected order field, page and order ID if a real data
anomaly still remains.

    & .\.venv\Scripts\python.exe -m v4.esi_parallel_validation --region-ids 10000002,10000043 --workers 2 --no-reference

Only once these two targeted regions have status COMPLETE should you
perform a fresh full-universe census; this avoids wasting a second global
ESI API crawl while a fixable major-market input anomaly remains.
A complete fresh run omits --region-ids and --max-regions.

Expected data-quality rules: a verified HTTP 200 [] with X-Pages=1
is EMPTY_MARKET_CONFIRMED; never assume any 404 or an empty page within
X-Pages>1 is valid zero. Zero-remaining orders are non-actionable and
excluded with explicit counters. Unexpected price, identity, or quantity
values still FAIL with the offending field and a minimal order identifier.

## Review requirements before any source switch

1. Complete 200-status pagination across all enumerated ESI regions, with 404s explicitly assessed rather than invented as empty.
2. ESI order count, last EVE Ref order count, matching order IDs, ESI-only, EVE Ref-only, mismatched price, remaining quantity and Jita BUY count.
3. Oldest/newest official ESI Last-Modified, regional span and the reference snapshot timestamp and age.
4. Record HTTP 429/420/5xx, missing headers, pagination rollover and failed regions.
5. A separate comparison of relevant Jita depth and market candidates must be assessed before approving production migration.

Even on success the program always emits data_source_decision=DO_NOT_SWITCH_PRODUCTION. The one-off script never starts a scheduled job or sends Gmail/game mail. Share report.json or console summary to proceed.

Documentation:
https://developers.eveonline.com/docs/services/esi/best-practices/
https://developers.eveonline.com/docs/services/esi/pagination/x-pages/
https://developers.eveonline.com/docs/services/esi/rate-limiting/
https://developers.eveonline.com/blog/market-orders-rate-limit-rolls-out-on-february-24-2026
https://docs.esi.evetech.net/docs/scenarios/structure_markets.html
https://docs.everef.net/datasets/market-orders.html
