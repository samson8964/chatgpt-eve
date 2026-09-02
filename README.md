# EVE BPC Arbitrage Scanner

自动扫描 EVE Online Tranquility 全服公开 BPC 合同，寻找“买 BPC → 在 Jita 买材料 → 高安低 SCI NPC 工厂制造 → 立即卖给 Jita 买单”仍有利润的机会。

## 自动运行

GitHub Actions 每天运行两次：

- 北京时间 08:30
- 北京时间 20:30

也可以在 **Actions → EVE BPC arbitrage scan → Run workflow** 手动触发。

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
- 自动制造地点目前只选择 The Forge 内、Jita 15 跳以内的高安 NPC Factory。
- 真旗舰（Rorqual / Carrier / Dread / FAX 等）和超级旗舰不进入自动主榜，避免高安制造/交货误判。
- 合同与市场快照不是秒级；真正买合同前仍应在客户端确认 BPC、价格和成品买单。

## 可调参数

可以在 GitHub Actions 的环境变量或脚本顶部调整，例如：

- `MIN_NET_PROFIT`
- `MIN_NET_ROI`
- `ACCOUNTING_LEVEL`
- `HIGHSEC_HAUL_ISK_PER_M3`
- `HIGHSEC_MAX_JUMPS_FROM_JITA`
