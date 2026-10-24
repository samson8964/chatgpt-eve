# V4 Independent Upstream Snapshot Audit

Goal: quantify actual EVE Ref market/contract snapshot ages and check regional omission signals against independent live ESI. A successful local file download is not proof of complete upstream ESI pages.

Read-only modules: v4.source_freshness_audit (no network) and v4.upstream_integrity_audit (public ESI GET only). Neither modifies the Windows hourly scanner, contract/market rules, database, mail or credentials.

Quick start on Windows (PowerShell):

    Set-Location (Join-Path $HOME 'EVE-V4-Code')
    git pull --ff-only
    & .\.venv\Scripts\python.exe -m v4.source_freshness_audit --deep
    $out = Join-Path $HOME 'EVE-V4-Data\audit\upstream-integrity.json'
    & .\.venv\Scripts\python.exe -m v4.upstream_integrity_audit --probe-all-regions --region 10000060 --output $out
    $r = Get-Content $out -Raw | ConvertFrom-Json
    $r.market_archive_global
    $r.live_esi.potentially_missing_market_regions
    $r.live_esi.region_order_id_reconciliation | Format-List

The first module reads compressed archive metadata, market HTTP Last-Modified distribution and contract scrape_start/scrape_end. The second counts every market order by EVE Ref region and cache timestamp; probes first-page ESI markets for all ESI region IDs, and fetches all pages of the requested region (default one named Delve, region 10000060).

Region conclusions are strict:
- MATCH_SAME_CACHE_GENERATION: same HTTP Last-Modified for archived region and all ESI pages; order IDs, remaining volume, type, price, locations and sides matched.
- DISCREPANCY_SAME_CACHE_GENERATION: same generation yet order count/IDs/values differ, a strong completeness signal requiring investigation.
- INCONCLUSIVE_VERSION_MISMATCH: ESI has refreshed between the archived scrape and independent query or pagination changed. Do NOT count differences as missing archived orders.
- potentially_missing_market_regions: present in current live first-page ESI but missing any archive rows. This is a hypothesis until cache timestamps align; zero-order regions are not expected in the archive.
- SKIPPED_PAGE_LIMIT: requested market region too large for configured safe page limit, not silently accepted as complete.

Known limitations: ESI region endpoints don't expose most privately owned player-structure markets; the three authorized 4-H/C-J/O4T feeds are verified separately by local page counts, not this public-region check. Upstream EVE Ref archived data could be missing source orders without a known same-generation live comparison; live prices cannot be reconstructed for a past snapshot. Never assert that all 113+ visible ESI regions have live sell orders.

Official sources:
- https://docs.everef.net/datasets/market-orders.html
- https://docs.everef.net/datasets/public-contracts.html
- https://developers.eveonline.com/docs/services/esi/pagination/x-pages/
- https://developers.eveonline.com/docs/services/esi/rate-limiting/