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

