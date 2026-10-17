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

## 通过后行动顺序

1. 审计异常星域，确认旧快照独有订单是否高度集中于特定站点/类型及交易方向。
2. 审计吉他买单前五价格档位及数量；若仅总数相近但可成交深度差异很大，优先调查缓存与数据转换。
3. 为第二轮影子机会模拟增补原始 `min_volume` 和 `range`，使用完全相同的 V4 正式引擎读取两个源，不编写新的简化利润计算程序。
4. 仅当覆盖、新鲜度、报价结构、利润结果都通过，才申请切换官方 ESI 优先；合同采集独立解耦，避免合同 EVE Ref 延迟继续阻塞市场提醒。

生产数据源切换和自动邮件逻辑必须另外经用户批准。