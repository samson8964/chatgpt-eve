# 74L2-U BANESTAR staged V4 market rollout

Structure: 74L2-U - BANESTAR - BALLS DEEP EDITION (S0B Holdings)
Location ID: 1050474463169

## Permission evidence
2026-10-21 first-page probe: main HTTP403, cj HTTP200, dc HTTP200.
The user has a separate character with docking access; use the new dedicated BANESTAR SSO profile instead of replacing main/cj/dc. Existing cj/dc 200 first-page results are not proof that the intended character has granted SSO access.

## Safety gate
The V4 station registry (v4/structure_registry.py) keeps the original
three stations by default. Git pull alone does NOT enroll BANESTAR.
The local Windows user must explicitly create
%USERPROFILE%\EVE-V4-Data\config\banestar-market.enabled
containing exactly ASCII APPROVED_1050474463169 (no byte order mark).
No scheduled task definition is changed.

## 1. Pull and offline regression tests
PowerShell:
    $repo = Join-Path $HOME 'EVE-V4-Code'
    git -C $repo pull --ff-only
    if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
    Set-Location $repo
    & .\.venv\Scripts\python.exe -m unittest v4.tests.test_banestar_enrollment v4.tests.test_candidate_station_probe v4.tests.test_esi_private_source_jita_ab v4.tests.test_local_service v4.tests.test_local_service_fail_closed v4.tests.test_market_station_integration v4.tests.test_opportunity_push v4.tests.test_structure_transport

Do not activate on any failed test.

## 2. Full-page one-station canary
    & .\.venv\Scripts\python.exe -m v4.candidate_station_full_probe

This fetches all pages for only 74L2-U using the new banestar profile.
It validates page count, structure ID and unique order IDs; only aggregate
counts are printed. Individual private orders, prices, keys and bodies are
never saved or printed. Target status FULL_BOOK_VALIDATED_NOT_ENROLLED.
Confirm active_sell_orders and distinct_sell_type_ids > 0.
HTTP200 page one alone is insufficient.

## 3. Explicit activation AFTER review of test and canary results
    $cfg = Join-Path $HOME 'EVE-V4-Data\config'
    New-Item -ItemType Directory -Force -Path $cfg | Out-Null
    $flag = Join-Path $cfg 'banestar-market.enabled'
    [System.IO.File]::WriteAllText($flag, 'APPROVED_1050474463169', [System.Text.Encoding]::ASCII)
    & .\.venv\Scripts\python.exe -c "from v4.structure_registry import STRUCTURES; print(STRUCTURES)"

On subsequent launches the hourly shadow and opportunity jobs need all
four complete structure market books. Missing/partial lanes fail closed.
Existing Jita 4-4 BUY order-depth valuation, ROI/profit/stress and haul
assumptions remain unchanged. Validate structure docking/transport in-game
before trading.

## Verification
Check next opportunity-push report for banestar COMPLETE and
by_station['74L2-U']; check next full shadow manifest contains four
COMPLETE lanes and INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED.

## Rollback
    Remove-Item -LiteralPath (Join-Path $HOME 'EVE-V4-Data\config\banestar-market.enabled') -Force -ErrorAction SilentlyContinue

New scheduled Python processes return to the original three stations.
Do not touch Cloudflare KV tokens, structure ACL, existing tasks, or mail.

## Deployment
Git branch: prep/v4-windows-local-migration-20261013.
First deploy the updated Cloudflare Worker with the BANESTAR SSO endpoint; then visit https://eve-contract-opener.99617224.workers.dev/auth-banestar in a browser and select ONLY the new docking-capable EVE character, authorizing esi-markets.structure_markets.v1. The Worker uses new banestar_refresh_token/banestar_character_id/banestar_character_name KV keys; do not touch existing main/cj/dc/mail tokens. Verify the character name on the SSO success page. The URL will not work on production until Cloudflare Worker deployment succeeds. A deployment updates the whole Worker and must be carefully reviewed for unsynced live changes. Run node --test v4/tests/test_worker_banestar_auth.mjs locally before deployment. Python station registration happens
only on the Windows host after git pull and explicit opt-in.
