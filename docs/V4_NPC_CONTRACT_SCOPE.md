# V4 contract discovery: all highsec / lowsec NPC stations (2026-10-15)

## User-approved scope

- Preserve current two-hour-to-one-hour Windows V4 scanner schedule and existing
  MARKET opportunity universe (4-H, C-J, O4T and current authorised market lanes).
- CONTRACT opportunity discovery: scan fresh full-universe EVE Ref public-contract
  archive every run and assess item-exchange contracts whose pickup locations
  belong to **any NPC station in high-security (displayed 0.5-1.0) or
  low-security (displayed 0.1-0.4) space**, plus the existing user-authorised
  private structures. Exclude nullsec NPC stations (negative/zero security).
- CCP SDE `npcStations.jsonl` links NPC station IDs to solar systems; CCP SDE
  `mapSolarSystems.jsonl` provides securityStatus and region. Raw status >=0.45
  maps to in-game highsec; raw status >0 and <0.45 maps to in-game lowsec,
  accounting for CCP's displayed-security rounding.
- Do not use a station-ID numeric range as a proxy for NPC status or security.
- Full SDE NPC membership is a **one-time local setup prerequisite**; hourly
  scanners read `EVE-V4-Data/reference/npc-stations-high-low.json` only.
  Without it the scanner retains old scope, explicitly reporting
  `npc_catalog_status=NOT_INSTALLED_LEGACY_CONTRACT_SCOPE`. Never claim complete
  NPC coverage until installed.
- Jita 4-4 BUY order DEPTH remains the liquidation benchmark. Requested contract
  items/BPC/missing volumes/unverifiable cash are excluded as before.
- Contract RESEARCH mail: require calculated ROI **>=10%**, along with existing
  positive profit, positive buy-depth stress and positive investment. Preserve
  market and contract top-10 newest-FIRST email selection, recipient list and
  true scan-based first-seen timestamps. A research contract is NOT a verified
  executable trade.
- Lowsec NPC transport risk is higher. Nonlegacy SDE-verified highsec NPC
  pickup cost estimate: `15m ISK + 750 ISK/m³`. Lowsec NPC: `50m ISK +
  2500 ISK/m³`. These are **conservative modelling assumptions**, not actual
  quotations and not route verifications. Previously approved Amarr/Dodixie
  station routes and the three authorised private structures retain legacy
  haul models. Never treat remote pickups as zero-cost. Actual transport
  market/risk and access need independent review before acting.
- Research-only and existing per-run idempotency: no LIVE action mode, order
  placement, new scan task or extra scheduled job is authorised.

## One-time Windows setup

Update code from existing V4 branch, and build the local NPC index:

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
& .\.venv\Scripts\python.exe -m v4.npc_station_catalog --install
& .\.venv\Scripts\python.exe -m v4.npc_station_catalog
& .\.venv\Scripts\python.exe -m unittest v4.tests.test_npc_station_catalog v4.tests.test_discovery_history v4.tests.test_unified_review -v
```

The first command downloads CCP official SDE JSONL zip once and parses the two
needed universe files. The temporary ZIP is deleted after atomic catalog
creation; storage remains outside the Git repo. If that official download
fails, you can manually download the same published ZIP and pass
`--sde-zip C:\path\to\eve-online-static-data-3579973-jsonl.zip`
with `--install`. Do not attempt to manufacture unknown stations.

Use the following PowerShell **after the next successful scheduled scan**:

```powershell
$run = Get-ChildItem "$HOME\EVE-V4-Data\runs" -Directory |
    Where-Object { Test-Path (Join-Path $_.FullName 'deep_shadow.json') } |
    Sort-Object Name -Descending | Select-Object -First 1
$report = Get-Content (Join-Path $run.FullName 'deep_shadow.json') -Raw | ConvertFrom-Json
$report | Select-Object npc_catalog_status,npc_catalog_sde_version,
    npc_catalog_highsec_stations,npc_catalog_lowsec_stations,
    npc_contracts_approved_for_deep_analysis,
    contract_approved_locations_examined
```

The expected scope status is `INSTALLED_SDE_FULL_NPC_HIGH_LOW`. Check actual
per-run scan duration and Gmail+game-mail receipts before concluding the new,
substantially larger contract evaluation comfortably fits the one-hour cycle.
Do not assume CI on synthetic fixtures proves live throughput or source freshness.

## Source references

CCP official SDE zip (2026-10-06 build 3579973):
`https://developers.eveonline.com/static-data/tranquility/eve-online-static-data-3579973-jsonl.zip`

Security rounding: `https://developers.eveonline.com/docs/guides/system-security/`.
SDE JSONL fields: `https://sde.riftforeve.online/schema/npcStations/`,
`https://sde.riftforeve.online/schema/mapSolarSystems/`.
