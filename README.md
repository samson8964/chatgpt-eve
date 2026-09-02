# EVE BPC Arbitrage Scanner

自动扫描 EVE Online Tranquility 全服公开 BPC 合同，寻找“买 BPC → 在 Jita 买材料 → 高安低 SCI NPC 工厂制造 → 立即卖给 Jita 买单”仍有利润的机会。

## 自动运行

GitHub Actions 每天运行两次：

- 北京时间 08:30
- 北京时间 20:30

也可以在 **Actions → EVE BPC arbitrage scan → Run workflow** 手动触发。

## 快速两级漏斗

为了避免对大量低价值 BPC 做昂贵的制造费和市场历史请求，当前默认使用快速模式：

### 第一层：廉价粗筛

只保留：

- 公开 `item_exchange` 合同
- 合同内全部交付物都是 BPC，不包含请求物品/BPO/杂物
- NPC 空间站合同
- 非真旗舰、非超级旗舰
- 单一成品类型（允许多张同类 BPC）
- 一批成品当前 Jita 买盘价值至少 30M ISK
- 扣除合同价和 Jita 材料深度后的粗利润至少 10M ISK
- 粗 ROI 至少 5%
- 当前 Jita 买盘能完整吃下一批成品

按粗利润排序后最多只保留前 150 个候选。

### 第二层：流动性 + 精算

前 150 个候选先查 30 日成交量；如果一批产量超过约 2 天的 30 日日均成交量，则提前排除。之后才进入昂贵精算：

- Jita 原材料真实卖盘深度
- 低 SCI 高安 NPC 工厂制造安装费
- 交易税
- 当前成品买盘深度和盈亏平衡买价
- 7/30 日市场历史
- 机会持续性和评分

默认只比较 The Forge 内 Jita 15 跳以内、SCI 最低的 2 个高安 NPC Factory。

最终主榜要求净利润至少 10M、净 ROI 至少 8%。游戏邮件进一步只推送净利润至少 20M、ROI 至少 8%、买盘容量至少 1 批的前 5 个机会；如果本轮没有强机会，也会发送“扫描完成、暂无强机会”的状态邮件。

## 当前结果

运行结果保存在：

- `results/latest/ranked_opportunities.csv`：去重后的主榜，优先看这个
- `results/latest/all_executable_scored.csv`：所有通过精确复核的合同
- `results/latest/product_watchlist.csv`：按商品汇总的观察表
- `results/latest/excluded.csv`：被排除合同及原因
- `results/latest/meta.json`：本次数据快照时间、工厂候选等元数据
- `results/state/opportunity_history.csv`：跨天积累的套利历史，用于判断持续性

## 利润口径

主榜净利润已经扣除：

- BPC 合同价格
- 按 Jita 4-4 卖盘深度购买原材料
- 制造安装费
- Accounting V 对应的即时成交交易税
- 可配置运输费（默认 0）

另外加入：

- 7/30 日成交量与 VWAP
- 当前买价相对 30 日 VWAP 的偏离
- 一批产量占 30 日日均成交量的比例
- 当前盈利买盘能容纳几份同类合同
- 过去 7 天机会持续率
- 机会评分和分类

## 当前限制

- 默认只考虑 NPC 空间站合同，避免玩家建筑停靠权限风险。
- 自动制造地点只选择 The Forge 内、Jita 15 跳以内的高安 NPC Factory。
- 真旗舰（Rorqual / Carrier / Dread / FAX 等）和超级旗舰不进入自动主榜。
- 快速模式主动放弃多成品 BPC 杂包和过低流动性机会，目标是提高实际可执行性和扫描速度，而不是理论上零遗漏。
- 合同与市场快照不是秒级；真正买合同前仍应在客户端确认 BPC、价格和成品买单。

## 可调参数

可通过 GitHub Actions 环境变量调整，例如：

- `MIN_NET_PROFIT`
- `MIN_NET_ROI`
- `PREFILTER_TOP`
- `PREFILTER_MIN_GROSS_REVENUE`
- `PREFILTER_MIN_ROI`
- `PREFILTER_MAX_OUTPUT_DAYS_30D`
- `ACCOUNTING_LEVEL`
- `HIGHSEC_HAUL_ISK_PER_M3`
- `HIGHSEC_MAX_JUMPS_FROM_JITA`
