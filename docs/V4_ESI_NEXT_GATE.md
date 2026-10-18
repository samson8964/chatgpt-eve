# V4 ESI 全市场验证：下一步离线审计

本阶段先利用已经完整保存的官方 ESI 1559428 条订单和 EVE Ref 1590543 条历史有效订单，定位报价差异和异常星域。**全程只读、离线，不启用新采集、不触发任何机会邮件，也不修改正式 V4 任务和 SQLite 账本。**

## Windows 运行

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
& .\.venv\Scripts\python.exe -m unittest v4.tests.test_esi_market_depth_audit -v
& .\.venv\Scripts\python.exe -m v4.esi_market_depth_audit --run 20261017T220739Z-69e03d4c
```

输出文件：`%USERPROFILE%\EVE-V4-Data\esi-parallel-validation\20261017T220739Z-69e03d4c\depth_difference_audit.json`。

## 输出和解释

- 抽查异常星域 10000030、10000027、10000014、10000066、11000004、10000010 的仅 EVE Ref、仅 ESI 订单按空间站和买卖方向的分布，以及全宇宙仅 EVE Ref 订单最多的星域。
- 比较吉他 4-4 买单商品种类、相同商品最优买价变更、前 **五个不同报价档位** 的数量和价格（不是五张随机订单，也不是忽略深度的简单平均）。
- 将已有的上一轮成功 EVE Ref 作为历史对照；它与 ESI 抓取时间不同，因此某个数据源仅有的订单并不是自动证明其数据缺失。
- 只对 `PUBLIC_ESI_REGIONS_COMPLETE` 且所有星域验证无失败的归档运行；没有证据就拒绝输出正常覆盖结论。
- 当前比较库仅存 `order_id / region_id / location_id / type_id / is_buy_order / price / volume_remain`，未完整保存 `min_volume / range`。因此不得据此给出 V4 真实成交利润或实际可交易候选。需要下一轮新鲜订单归档保留这些字段，再共用正式 V4 的经济模型、授权站点、体积、运费、税费和压力利润，完成相同输入标准下的候选数量及差异验证。

## 2026-10-18 深度审计实测结论

已收到 depth_difference_audit.json （run 20261017T220739Z-69e03d4c）：
- ESI 1,559,428 vs EVE Ref 1,590,543，匹配订单ID 1,530,213，占 ESI 98.127%。
- 吉他双方共有17,680个带买单商品；最优买价不同4,992种，前五价格档位数量不同5,500种。这些是不同时间快照的变动，不能据此断定接口故障。
- 10000030 EVE Ref 独有11,884单，其中玩家建筑 1022167642188 卖单9,721及买单313，总计10,034单，占84.43%。10000027/10000014/10000066的独有单几乎全部集中在玩家建筑。这符合公开ESI不提供全部Upwell建筑订单的覆盖差异，且说明正式切换时绝不能丢弃独立授权的玩家建筑市场链路。
- 正式生产 EVE Ref 数据源暂时不变；截图/JSON总结不能证明同V4净利润结果。

已经将新采集器的逐单独立 JSONL 归档扩展为保存 min_volume、range、volume_total；原有 comparison.sqlite3 的7列只读对账模式不变；此前的旧归档不会凭空获得缺失字段。

先做轻量真实 ESI 字段取样（约一个中小星域；不是完整市场扫描）：

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
& .\.venv\Scripts\python.exe -m unittest v4.tests.test_esi_parallel_validation -v
& .\.venv\Scripts\python.exe -m v4.esi_parallel_validation --region-ids 10000001 --workers 2 --no-reference
```

只有取样确定字段齐全、没有分页/类型问题后，才考虑下一轮全量归档和同算法影子利润验证。特别注意在下一轮模型中只与正式 V4 相同的许可 NPC 站点和独立授权私有站点匹配，不应假装 ES I 公开数据覆盖全部可访问玩家建筑市场。

## 通过后行动顺序

1. 审计异常星域，确认旧快照独有订单是否高度集中于特定站点/类型及交易方向。
2. 审计吉他买单前五价格档位及数量；若仅总数相近但可成交深度差异很大，优先调查缓存与数据转换。
3. 为第二轮影子机会模拟增补原始 `min_volume` 和 `range`，使用完全相同的 V4 正式引擎读取两个源，不编写新的简化利润计算程序。
4. 仅当覆盖、新鲜度、报价结构、利润结果都通过，才申请切换官方 ESI 优先；合同采集独立解耦，避免合同 EVE Ref 延迟继续阻塞市场提醒。

生产数据源切换和自动邮件逻辑必须另外经用户批准。
## Same-engine market opportunity shadow parity (2026-10-18)

The one-region field smoke-test `20261017T223910Z-0854a10e` has **passed**:
15,559 orders / 16 pages / 17 HTTP 200 responses, 7.84 seconds; all
active orders retained `min_volume`, `range` and `volume_total`.

An isolated comparison runner now uses the **production V4**:
- `v4.engine.Order.parse`
- `v4.market_execution.gross_depth_upper_bound` and the same 50M ISK prefilter
- `v4.engine.market_proof` with its quantity optimization, 10% ROI,
  volume density, sales tax and Jita bid-loss stress
- `v4.catalog.Catalog.volume` from the existing local catalog
- `v4.deep_scan.haul` and `known_station_regions` / secure route-jump
  metadata, using the same model on both historical input sources

**Scope matters**: Only existing approved *NPC* purchase venues Amarr
station 60008494 and Dodixie station 60011866 are compared to the
Jita 4-4 station's BUY depth. The authorized Upwell markets in 4-H,
C-J and O4T are NOT compared or replaced. Contracts / manufacturing
are unchanged. A policy pass is stored as a RESEARCH-ONLY shadow proof:
the user gets no market opportunity email from this module.

The old complete-run ESI JSONLs `20261017T220739Z-69e03d4c`
cannot be reused for this gate: they lacked exact `min_volume` and
`range`. To do one complete same-engine parity, first create a
NEW all-regions archive with those original fields:

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
& .\.venv\Scripts\python.exe -m unittest v4.tests.test_esi_same_engine_market_shadow -v
& .\.venv\Scripts\python.exe -m v4.esi_parallel_validation --workers 3
```

IMPORTANT: Run the following comparison **only if** the above complete
ESI run reports `status=PUBLIC_ESI_REGIONS_COMPLETE` and identifies
a pinned prior successful EVE Ref reference archive. The command prints a
new run ID; replace `<NEW_RUN_ID>` with that ID:

```powershell
& .\.venv\Scripts\python.exe -m v4.esi_same_engine_market_shadow --run <NEW_RUN_ID>
```

The runner refuses incomplete regions, incomplete order fields, missing
pinned EVE Ref archives and missing local catalog. It does not update
production. The output is one isolated file:

`%USERPROFILE%\EVE-V4-Data\esi-parallel-validation\<NEW_RUN_ID>\same_engine_market_comparison.json`

It compares candidate station/type pair sets, profit/stress/ROI/quantity
and why a model threshold passed on one historical book and not on the
other. Both books receive *identical* route and haul logic. It may call
a small number of **official ESI route and station metadata endpoints**
for route jumps, never the full market or contract API. The ESI orders
are archived at distinct five-minute cache times and EVE Ref orders
are from a different historical timestamp, so neither report proves
that an opportunity was executable live.

Do **not** use this workflow to declare complete parity of private Upwell
markets, contracts, or blueprint opportunities. Their own data lanes
must remain isolated, and official production source switching still
needs a separate approval.


## Single-region recovery of the 2026-10-18 06:56 CST run

Latest all-region run **20261017T225007Z-79cc75a2**:
- 114 attempted, 59 COMPLETE, 54 EMPTY_MARKET_CONFIRMED.
- **Only 10000028 FAILED: ESI_PAGINATION_VERSION_MISMATCH**.
- Saved 1,534,255 independently verified order rows, 1,629 pages.
- The missing region held 24,679 orders in the old EVE Ref snapshot. This historical value does not establish current liquidity.
- 1,704 HTTP 200; no HTTP failure or 429 limit was shown.
- Never reclassify this failed run as completed or the missing region as zero orders.

Avoid re-reading the same 113 independent regional archives:

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
& .\.venv\Scripts\python.exe -m unittest `
    v4.tests.test_esi_merge_single_region `
    v4.tests.test_esi_same_engine_market_shadow -v

# Target ONLY failed region without downloading all regions again.
& .\.venv\Scripts\python.exe -m v4.esi_parallel_validation `
    --region-ids 10000028 --workers 1 --no-reference
```

Inspect status PARTIAL_REGION_TEST_ONLY, regions[0].status COMPLETE, and
the newly printed patch run ID. If the targeted run fails, do not merge.
Next, substitute the targeted run ID:

```powershell
& .\.venv\Scripts\python.exe -m v4.esi_merge_single_region `
    --base-run 20261017T225007Z-79cc75a2 `
    --patch-run PATCH_RUN_ID
```

The merge reads the original comparison.sqlite3 in read-only mode,
checks the patch for duplicate order IDs, validates each regional archive
and creates a NEW independent report referencing immutable source files.
It never copies 1.5 million rows or alters the old full-run report.

Composite status is **SHADOW_MULTI_EPOCH_REPAIRED_COVERAGE**, deliberately
not PUBLIC_ESI_REGIONS_COMPLETE. Check its ESI Last-Modified span: this
is historical shadow research ONLY, not a coherent single-epoch census.
Even if the data are old or hours apart, no opportunity alert is allowed.

Run same production-market-engine historical NPC parity using the newly
printed composite run ID:

```powershell
& .\.venv\Scripts\python.exe -m v4.esi_same_engine_market_shadow `
    --run COMPOSITE_RUN_ID
```

This evaluates only approved NPC Amarr + Dodixie station asks against
Jita 4-4 BUY depth. It reuses the actual v4.engine.market_proof and
deep_scan.haul and writes same_engine_market_comparison.json. It may call
official station/route metadata, not market or contract data. Zero mail,
zero scheduled changes, zero authenticated player-station market writes.

Production source migration still needs a new coherent independent fresh
full-region census and separately authorized Upwell market coverage.

## 2026-10-18: Zero formal opportunities requires near-miss evidence

The actual `same_engine_market_comparison.json` on the immutable
multi-epoch run `20261017T231839Z-9c24d05b` returned:

- ESI 16 prefilter passes: 15 BELOW_GATE_OR_STRESS, 1 NO_PROFITABLE_MATCHED_DEPTH.
- EVE Ref 17 prefilter passes: all 17 BELOW_GATE_OR_STRESS.
- Both final formal gate sets empty; union of prefilter station/type candidates is 20.
- Only approved NPC Amarr 60008494 and Dodixie 60011866 were considered.
- No evidence supports weakening the 50m ISK, 10% ROI, 2000/m3,
  3.375% sales tax or top-Jita-bid-loss stress policy based on this output.

The old JSON withheld *all* 20 prefilter candidates because both final
gate sets were empty. Instead, inspect precisely which constraints failed
without rescraping any market orders. This runs the SAME market_proof
on the SAME immutable archives and creates a distinct file, preserving
the previous comparison:

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
& .\.venv\Scripts\python.exe -m unittest `
    v4.tests.test_esi_same_engine_market_shadow -v
& .\.venv\Scripts\python.exe -m v4.esi_same_engine_market_shadow `
    --run 20261017T231839Z-9c24d05b --explain-existing
```

Read `same_engine_market_near_miss_audit.json`: all prefilter
station/type pairs, each source's original model reason, quantity,
profit, ROI, density, stress profit, haul cost, source and Jita VWAP,
plus each formal gate's threshold and explicit pass/fail status.

No market / contract / private structure requests or opportunity mail.
The V4 route metadata may be read for the same transport model.
Historical multi-epoch data remain research-only and never qualify for
production alert freshness. After analyzing rejection reasons, the next
business-relevant A/B comparison must hold the actual authorized Upwell
sell-order inputs (4-H, C-J, O4T) constant and change ONLY the Jita 4-4
BUY feed. This isolates pricing-source impact without recomputing
contracts or exposing private order books.

## 2026-10-18: real near-miss report and the next private-market research lane

The user supplied `same_engine_market_near_miss_audit.json` for composite run
`20261017T231839Z-9c24d05b`. Audited all 20 unique station/type
prefilter candidates (13 both feeds, 3 ESI only, 4 EVE Ref only).
The ESI model returned 16 prefilter candidates: 15 negative net, one
NO_PROFITABLE_MATCHED_DEPTH. The EVE Ref model returned 17 candidates:
16 negative and one positive (Dodixie, type ID 18789, quantity 5,
18,361,500 ISK modeled profit, 1.936% ROI, 18,168,250 ISK stress profit).
This positive is still below the approved 50m ISK net and stress and 10%
ROI thresholds. Every final formal alert set is empty.

Many pass the pre-tax, pre-haul optimistic gross-depth ceiling only to
fail the full model with quantity 1. This is consistent with a permissive
upper-bound prefilter (not evidence of an optimizer defect). Do not
weaken the 50m/10%/2000-per-m3/stress policy on this evidence.

### Authenticated 4-H/C-J/O4T identical-source Jita price-feed A/B

The new `v4.esi_private_source_jita_ab` runner uses **exactly one**
fresh complete authorized collection of existing 4-H/C-J/O4T structure
SELL books via the existing V4 credential/bridge. That same immutable
in-memory source book is independently valued against historical
Jita 4-4 BUY books archived under this composite ESI run (ESI and
its pinned EVE Ref), with existing `Order.parse`,
`gross_depth_upper_bound`, `market_proof`, volume catalog and
`deep_scan.haul`. The runner uses the same V4 source authorization IDs,
rejects any failed structure lane and writes only aggregate research
proofs plus SHA-256 book fingerprints; it never persists raw private
orders or bridge authentication keys. It does not call a new public
market/orders endpoint, scan contracts, modify V4 databases, change
timers or send mail.

To run on the user's Windows machine (with the same saved bridge
credential already configured for normal V4), outside of the scheduled
:23 scan if possible:

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
& .\.venv\Scripts\python.exe -m unittest `
    v4.tests.test_esi_private_source_jita_ab -v
& .\.venv\Scripts\python.exe -m v4.esi_private_source_jita_ab `
    --run 20261017T231839Z-9c24d05b
```

On success status is READ_ONLY_PRIVATE_SOURCE_FIXED_JITA_BUY_AB.
The runner prints the path of a new independent file in the composite
run folder, named `private_source_jita_ab_<timestamp>-<id>.json`.
Upload that **JSON summary** only. Never share bridge keys,
credential manager contents or private order raw page exports.

**Hard limitation:** private source asks are from this new run, while
both historic Jita books date from October 17 and EVE Ref is hours
older. Candidate pass counts are hypothetical retrospective sensitivity
analysis, *not executable opportunities*, not validation of live
source switching, and never eligible for automated alerting.

Only after reviewing the differences do we design a controlled live
fresh Jita-ESI book trial, isolated from production outbox, requiring
one synchronized source and price capture and direct verification of
actual executable lots.

## 2026-10-18 07:43+ CST: actual authorized 4-H/C-J/O4T price-feed A/B

User supplied `private_source_jita_ab_*.json` of run
`20261017T231839Z-9c24d05b`:

- All authorized lanes COMPLETE: 4-H 33,390 market orders (34 pages),
  C-J 52,697 (53 pages), O4T 6,974 (7 pages); 93,061 total active,
  71,442 SELL; 15,367 station/type sell pairs.
- SAME private SELL inputs against historical Jita BUY snapshots:
  ESI 32 optimistic depth-prefilter candidates (4-H 3, C-J 24, O4T 5);
  pinned EVE Ref 4 (4-H 1, C-J 3, O4T 0).
- Union 33: only ESI 29, only EVE Ref 1, both 3.
- FULL approved formal policy passes: ESI 0, EVE Ref 0.
- 4-H item 28352: ESI net 187.16m ISK, ROI 4.50%,
  stress fill unavailable (stress_profit=-1 sentinel, NOT -1 ISK loss).
- C-J item 28352: ESI net 587.16m, ROI 15.62%,
  stress fill unavailable: DO NOT mail as executable.
- C-J item 36: ESI net 68.82m, stress 68.58m, ROI 4.60%, fails ROI.
- O4T item 19111: ESI net 67.00m, ROI 35.08%,
  stress 44.10m, fails 50m stress floor.
- Original complete ESI source book is from 22:45:39-23:11:16 UTC.
  EVE Ref fixed old reference is 14:21:20 UTC; private markets collected
  23:43:43 UTC. The 32 vs 4 gap CANNOT isolate which source is better
  because the two price books are from different times.

### Fresh Jita-4-4 validation gate (no production changes)

New optional `--fresh-jita-run` to `v4.esi_private_source_jita_ab`:
pass a newly independently validated **only The Forge region 10000002**
ESI one-shot archive. It checks 10000002 COMPLETE, all archive counts,
all required economic fields, nonduplicate order IDs, page count,
Last-Modified UTC age <= 15 minutes AT PRIVATE COMPARISON TIME, and
only uses verified **Jita station 60003760 BUY** orders.

Leave original composite EVE Ref pinned as the historical control.
Only fresh ESI is different. Do not interpret EVE Ref as matched-current.
Private asks are separately fetched once (all three lanes must pass),
then both Jita buy feeds value the SAME asks through original market_proof.
New output `private_source_jita_fresh_ab_<stamp>-<id>.json` explicitly
includes the ESI archive run and verified timestamp. No mail, live
trade, public market re-query from this A/B process, or production write.

PowerShell run promptly after git pull and CI/tests passing:

```powershell
Set-Location (Join-Path $HOME 'EVE-V4-Code')
git pull --ff-only
& .\.venv\Scripts\python.exe -m unittest `
    v4.tests.test_esi_private_source_jita_ab -v

# Download ONLY Forge public regional market orders; all pages must agree.
$out = & .\.venv\Scripts\python.exe -m v4.esi_parallel_validation `
    --region-ids 10000002 --workers 1 --no-reference
$out | Write-Output
if ($LASTEXITCODE -ne 0) { throw 'Fresh Jita ESI collection failed' }
$line = $out | Where-Object { $_ -match '^REPORT\s+' } | Select-Object -Last 1
if (-not $line) { throw 'Fresh Jita report path missing' }
$file = $line -replace '^REPORT\s+', ''
$fresh = Get-Content -LiteralPath $file -Raw -Encoding UTF8 | ConvertFrom-Json
if ($fresh.status -ne 'PARTIAL_REGION_TEST_ONLY' -or `
    $fresh.regions[0].status -ne 'COMPLETE' -or `
    $fresh.requested_region_ids[0] -ne 10000002) {
    throw 'FRESH_JITA_ESI_REGION_INCOMPLETE'
}

# Do this immediately: ESI last-modified must be <=15 minutes old
# when the one-shot authorized private comparison FINISHES.
& .\.venv\Scripts\python.exe -m v4.esi_private_source_jita_ab `
    --run 20261017T231839Z-9c24d05b `
    --fresh-jita-run $fresh.run
```

If error FRESH_JITA_ESI_SNAPSHOT_TOO_OLD_OR_CLOCK_SKEW appears,
the old validated Forge book has expired for this **research** run.
Do not circumvent the guard; perform a new 10000002-only collection.
If a private lane fails, treat whole comparison as unavailable.

Share ONLY the generated `private_source_jita_fresh_ab_*.json`, not
credentials or raw private pages. Do not infer live tradeability.


## 2026-10-18 08:03 CST: fresh-Jita authenticated private-market shadow result

User supplied a completed `READ_ONLY_PRIVATE_SOURCE_FRESH_JITA_BUY_AB` report
for the same research base run `20261017T231839Z-9c24d05b`.
This is research-only: no alerts, no trading, no production feed change.

- Fresh Forge `10000002` ESI archive `20261017T235514Z-1a88e576`:
  403,196 active orders, 404 verified pages, **91,179 Jita 4-4 BUY orders**;
  official `Last-Modified` `2026-10-17T23:55:46Z`, age 7.813 minutes
  when the authorized 3-station collection completed.
- Private bridge captured from `2026-10-18T00:01:24Z` to
  `2026-10-18T00:03:34Z`: all three lanes COMPLETE;
  4-H 33,394 orders, C-J 52,644, O4T 6,974; 93,012 active,
  71,391 SELL and 21,621 BUY excluded from sourcing.
- Source station/type SELL pairs: 15,361. Against SAME private SELL inputs,
  recently archived official ESI Jita BUY book produces 99 gross-depth
  prefilter passes (4-H 12, C-J 73, O4T 14) and 3 `market_proof` full gate
  passes (O4T 2, C-J 1, 4-H 0). The pinned historical EVE Ref
  (2026-10-17T14:21:20Z) produces 4 prefilters and 0 final passes.
  Candidate union 99, classification 96 NEITHER_PASS and 3 ESI_ONLY_PASS.
  This comparison **does not establish contemporaneous source superiority**.

### Three model-qualified candidates (all retrospective)

| Location / type | Qty | Net profit ISK | ROI | Stressed net ISK | Estimated haul ISK |
|---|---:|---:|---:|---:|---:|
| O4T / 41059 (Domination Heavy Stasis Grappler) | 13 | 184,553,000 | 12.2608% | 181,364,375 | 10,325,000 |
| O4T / 19111 (Corpum A-Type Medium Energy Nosferatu) | 3 | 75,735,137.5 | 39.6483% | 75,696,487.5 | 10,007,500 |
| C-J / 96789 (Mutated Blood Sample; 2026 event item) | 8,025 | 55,231,867.1875 | 10.000224% | 54,533,993.125 | 10,040,125 |

**IMPORTANT COST-SENSITIVITY TEST**: The V4 private-structure transport
estimate is `10m + 500 ISK × m3`, not a real safe transport quote.
When an added expense `x` reduces modeled profit by `x` and increases
total invested cost by `x`, the 10% ROI gate becomes
`(profit - x)/(capital + x) >= 10%`.
The maximum extra unmodeled expense before *any* profit/ROI/stress threshold
fails is approximately **30.94m ISK** for O4T/41059 (ROI limited),
**25.70m** for O4T/19111 (stressed profit limited), and only **1,127 ISK**
for C-J/96789 (ROI limited). These are sensitivity calculations from the
report, not validated courier prices or remaining ISK after game fees.

Some near-misses have larger unstressed profit than 3 qualified ones:
C-J/28352 587.16m ISK modeled normal net, but stress fill unavailable
(`stress_profit=-1` means nonexecutability, NOT a real -1 ISK quote);
C-J/39 ~388.52m net but ROI ~7.6%, below 10%. Do not bypass gates.

### Next strictly isolated acceptance gate, before any production approval

1. Validate exact source SELL and Jita BUY order IDs, prices, quantities,
   `min_volume` and order range of the **three** prioritized type IDs
   with freshly collected authorized structure books and a fresh official
   Jita BUY type-filtered/book snapshot. The existing summary does not
   include raw private order IDs by design; never disclose credentials.
2. Check collateral-adjusted hauling quotations, delivery risk/route,
   taxes, and cash capital; the 10m+500/m3 proxy can materially overstate
   net and ROI, especially C-J/96789, whose ROI buffer is ~1,127 ISK.
3. Require two independent fresh validations separated by the 5-minute
   official ESI cache rollover, and reject changed/missing execution
   liquidity. Only confirmed opportunity proofs may be considered for
   a *separately approved* production change.
4. Do not substitute the >9-hour-old EVE Ref BUY book or saved historical
   opportunities for current executable quotes. Preserve the contracts
   and existing 4-H/C-J/O4T data lanes as-is; mail/scheduler unchanged.

This finding establishes the **technical and economic promise** of the
fresh ESI Jita valuation approach, but not a verified live executable
trade or authorization to change production.
