# EVE V4 | Hunter five private-structure procurement scout | 2026-11-09

## Scope and status

The user supplied a screenshot of six locations. **Jita is excluded**.
Read-only procurement targets, in screenshot order:

| Lane | Screenshot station | Exact structure ID | Provenance | Screenshot route count |
| --- | --- | --- | --- | --- |
| banestar | 74L2-U - BANESTAR - BALLS DEEP EDITION | 1050474463169 | Existing V4 registry | 33 |
| cj | C-J6MT - 1st Taj Mahgoon | 1049588174021 | Existing V4 registry | 72 |
| o4t | O4T-Z5 - Dracarys. Prime | 1040804972352 | Existing V4 registry | 0 |
| r_arkn | R-ARKN - BIG MOM | 1048663825563 | Public EveSynapse structure directory; requires ESI validation | 1 |
| ualx | UALX-3 - Mothership Bellicose | **unknown** | The screenshot contains the name, not the structure ID | 29 |

These 33/72/0/1/29 numbers are **route counts on the source
screenshot**, not market orders, monthly trading volume, or purchasable
opportunities. The precise Upwell ID for UALX must be supplied from an
in-game structure showinfo link or otherwise verified source. Do not
substitute the solar-system ID (30004807).

The user now writes "Arb Hunter"; on 2026-11-08 they called the new
character "Abr Hunter". The diagnostic requires **exact authorization
identity** and fails closed if the Worker stored name differs. Do not
silently treat these spellings as equal.

## Auth architecture

The current Cloudflare Worker already supports an independent `dc`
SSO token with scope `esi-markets.structure_markets.v1`.
CCP's ESI structure-market endpoint permits a single authorized
character to read every structure to which it has market access:
`GET /latest/markets/structures/{structure_id}/?page=...`.
It is **not necessary to create five EVE SSO authorizations**.
One `/auth-dc` authorization can service the five read-only requests,
subject to live structure ACL checks.

Stage 1 deliberately reuses the **existing** `dc` profile and introduces
no Worker changes/redeploy. Existing V4 production `cj`, `dc`,
`banestar` source registry and mail sender remain unchanged.
Do not change `/auth-cj`, `/auth-banestar`, or `/auth-mail`, and
do not click any `/logout-*` routes.

## Operator handoff 1: EVE login (requires user)

Visit the existing deployed
https://eve-contract-opener.99617224.workers.dev/auth-dc
and authorize the correct **exact** Hunter EVE pilot with
`esi-markets.structure_markets.v1`.
The SSO callback should show the selected pilot name and the Worker
main status page should show the same pilot in "DC影子市场授权".
This replaces the old `dc` identity only; old LadyBaBa is retired.
It does not authorize any automatic trading.

The public status page cannot be read from this environment; this step
must be verified in the user's browser.

## Operator handoff 2: Windows one-page safe preflight

Only use the authorized existing V4 Windows user profile with its
Windows Credential Manager bridge key. Do not paste an API key/token into
chat or scripts.

```powershell
$repo = Join-Path $HOME 'EVE-V4-Code'
if ((Get-ScheduledTask -TaskName 'EVE-V4-Shadow').State -eq 'Running') {
    throw 'Scheduled scanner currently Running: do not update checkout'
}
$branch = git -C $repo branch --show-current
if ($branch -ne 'prep/v4-windows-local-migration-20261013') {
    throw "Unexpected branch: $branch"
}
git -C $repo pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
Push-Location $repo
try {
  & .\.venv\Scripts\python.exe -m v4.hunter_purchase_probe --expected-name "Arb Hunter"
} finally {
  Pop-Location
}
```

If the actual pilot is **Abr Hunter**, change only the
`--expected-name` value to the exact EVE name confirmed at the SSO
callback. Do not reuse a misleading name.

Expected first-run result:
- `authorized_character` is the exact user-owned Hunter character.
- `banestar`, `cj`, `o4t`, `r_arkn` each report `PAGE1_OK`.
- `ualx` reports `NEEDS_EXACT_STRUCTURE_ID` until supplied.
- `purchase_enabled=false`, `orders_saved=false`,
  `production_registry_changed=false`.

`PAGE1_OK` means the Worker/ESI returned a valid page of orders, not
that every page can be retrieved or any item is worth buying. A market
may legitimately have 0 orders.

## Operator handoff 3: UALX exact structure ID and full pagination

Have the user copy the in-game showinfo link of the exact
`UALX-3 - Mothership Bellicose` Keepstar, often formatted
`<url=showinfo:<type_id>//<structure_id>>...` (the structure ID is the
large 13-digit integer after `//`). Do not infer this from screenshot.

Then execute a five-station **first-page** check:

```powershell
& .\.venv\Scripts\python.exe -m v4.hunter_purchase_probe --expected-name "Arb Hunter" --ualx-id <EXACT_UPWELL_STRUCTURE_ID>
```

Only after **all five report** `PAGE1_OK`, run:

```powershell
& .\.venv\Scripts\python.exe -m v4.hunter_purchase_probe --expected-name "Arb Hunter" --ualx-id <EXACT_UPWELL_STRUCTURE_ID> --full
```

Expected `FULL_PAGES_COMPLETE`; each station returns
`pages_fetched==pages_reported`. No orders are persisted, no trading
and no mail is sent. `--full` may take substantially longer than page 1.

If 401/403 occurs, inspect identity, bridge key vs OAuth, actual in-game
market permission and whether the structure has changed owner/ACL.
A status 200 with incomplete pages is not an accepted completed scan.

## Stage 2 after successful user evidence (not yet deployed)

Only after validated exact UALX ID, real Hunter identity, and complete
five-station pages:

1. Add and gate R-ARKN and UALX lanes in the single V4 structure registry.
2. Decide whether existing three source profiles remain or migrate to
   `dc` *after* verified no loss of access.
3. Reuse existing V4 market-to-Jita buy-depth valuation, cash floor
   50M ISK, ROI ≥10%, and 2,000 ISK/m³ policy, while preserving
   stress-test, freshness, partial-coverage and no-live-execution safeguards.
4. Run exactly one shadow scan first and reconcile each lane's pages,
   order count, and source integrity. Do not automatically enable
   `EVE-V4-Opportunity-Push`.
5. Record the state and results in Airtable; no change to the approved
   project's final goal or major architecture is implied by this read-only
   coverage expansion.

The V4 opportunity engine is a *scanner and research* workflow: ESI
market-read access cannot buy or accept a trade for the pilot.

References:
- CCP ESI structure markets: https://docs.esi.evetech.net/docs/scenarios/structure_markets.html
- CCP EVE SSO: https://developers.eveonline.com/docs/services/sso/
- Public R-ARKN listing: https://evesynapse.app/structure/?structure=1048663825563
