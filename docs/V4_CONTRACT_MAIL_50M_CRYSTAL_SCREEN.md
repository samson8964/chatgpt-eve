# V4 contract mail noise reduction (2026-10-16)

User-authorized contract-only research-mail changes:

- Enforce **calculated net profit >=50,000,000 ISK**, inclusive.
  This is after the scan's existing sales tax and haul model, using Jita
  4-4 BUY-depth liquidation. The previously approved >=10% ROI,
  positive stress and other quality gates remain in place.
- Exclude contracts whose **energy turret laser crystals are >=50% of
  the included cargo's Jita BUY-depth liquidation value**. Group IDs:
  - 86: ordinary/faction Frequency Crystal
  - 374: Advanced Beam Laser Crystal (Aurora/Gleam)
  - 375: Advanced Pulse Laser Crystal (Scorch/Conflagration)
- Value share is computed with the same exact quantity-aware Jita buy
  depth used for contract valuation. Exclude crystal-dominated mixed
  bundles, but **retain** high-value mixed bundles that merely include a
  minority of crystals. Do not accidentally include mining crystals,
  blueprint items or other charge categories.
- Reject research leads if included-item group identity or Jita BUY
  depth is unverified, rather than assuming an unknown group is not a
  laser crystal. The deep scan stores `energy_crystal_value_share`
  and `energy_crystal_share_verified` on contract proofs for auditing.
  Historical proof records that lack metadata are not backdated as a
  new qualifying discovery. Existing per-run email receipts and
  10-per-category newest-first selection remain unchanged.
- The `v4/catalog.py` cached compressed EVE Ref reference-data schema
  upgrades from 1 to 2, now including the source `group_id` metadata.
  **First new-version scan fetches one bulk reference archive to rebuild**
  the local catalog if the cache is still schema 1. Network errors
  fail closed, not silently allow category-unknown contracts.
- Scanner still analyzes/records historical proofs; this policy
  decides **which contract leads appear in Gmail/game research digests**.
  Market orders, market profitability thresholds, 4-H/C-J/O4T lanes,
  high/low NPC contract source scope, email recipients, scan schedule,
  and research-only/no-live-execution remain unchanged.

## Local installation and verification

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only

# One-time migration of the saved static item catalog; downloads an
# EVE Ref reference archive only if this is an older schema.
& .\.venv\Scripts\python.exe -c "from v4.catalog import ensure_catalog; c=ensure_catalog(); assert c.group_id(23071)==86; assert c.group_id(12559)==374; assert c.group_id(12563)==375; print('CATALOG_CRYSTAL_GROUPS_OK', c.meta.get('inventory_group_known'))"

& .\.venv\Scripts\python.exe -m unittest v4.tests.test_contract_content_policy v4.tests.test_catalog v4.tests.test_discovery_history v4.tests.test_contract_review_mail -v
```

The next completed local V4 scan should create contract proofs with
`energy_crystal_value_share`, and its `deep_shadow.json` should report
`contract_crystal_screen_basis: JITA_BUY_DEPTH_BY_INVENTORY_GROUP`.
For the emails check each net profit >=0.50亿 and ROI>=10%;
excluded crystal-heavy contracts must not occupy the limited top-10
positions.

This does **not** establish live prices, actual route safety, or
contract availability. All valuations remain snapshot RESEARCH.
