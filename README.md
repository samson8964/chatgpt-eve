# EVE Contract Arbitrage System

面向 **EVE Online Tranquility** 的公开合同套利扫描与 EVE Mail 推送系统。

当前有两条独立主线：

1. **BPC 蓝图捡漏**：主要寻找复制蓝图本身的每流程合同价格显著低于同类可比价格的机会，同时保留制造后全成本利润作为第二参考。
2. **单件 / 多件现货合同捡漏**：拆解公开 `item_exchange` 合同并按 Jita 市场深度重新估值，寻找整包错价和可兑现套利。

两条线独立排名、独立做合同存活复核、独立发送 EVE 游戏邮件，每轮各最多 **TOP 10**。

---

## 自动运行

GitHub Actions 默认每天北京时间：

- **08:35**
- **20:35**

```text
35 0,12 * * *
```

也支持在 Actions 页面手动触发。

完整流程：

```text
EVE Ref 全服公开合同 / 市场快照
        ↓
BPC 制造利润扫描
        ↓
全星域 BPC 每流程自身价值扫描
        ↓
全星域现货合同扫描
        ↓
不可达星系过滤
        ↓
一键 EVE 合同链接
        ↓
发送前 ESI 合同存活复核
        ↓
BPC TOP10 + 现货 TOP10 两封独立邮件
        ↓
保存结果 / 历史状态
```

---

# 1. BPC 蓝图捡漏：自身价值优先

BPC 线不再要求一张蓝图必须先成为“制造强机会”才有资格被推荐。

核心判断变成：

```text
当前 BPC 合同价格 / 总流程数
        ↓
当前每流程买入价
        ↓
与全服同种 BPC 的可比每流程合同价格比较
        ↓
如果折价显著，则进入 BPC 价值候选
```

因此特殊、稀有、流程类、Jita 没有正常蓝图市场报价的 BPC，也可以通过合同市场本身得到估值。

## BPC 合同地点不限高安

**BPC 的合同领取地点不以安全等级作为硬过滤条件。**

可进入候选的地点包括：

- 高安
- 低安
- NPC 00
- 可解析且星门可达的玩家建筑 / 主权 00

低安和 00 只影响风险标签和排序，不会因为安全等级低直接删除。

真正会被剔除的是：

- 无法解析到有效星系
- 从 Jita 无法得到普通星门最短路线
- 明确不可达的位置

玩家建筑即使能解析，也仍需要人工确认 Dock 权限。

> **合同领取地点** 与 **制造地点** 是两件不同的事。当前制造利润模型仍默认把蓝图运回 Jita 周边低 SCI 高安 NPC 工厂制造；这不会限制 BPC 合同本身可以出现在哪。

---

# 2. BPC 每流程合同市场估值

对于每个“纯 BPC、单一 Blueprint Type”的公开出售合同，系统计算：

```text
当前每流程价格
= 合同总价 / 合同内该种 BPC 的总流程数
```

多个相同 Blueprint Type 的 BPC 可以放在一个合同中，系统会合并所有复制品的流程数。

系统随后寻找同一种蓝图的其他公开 BPC 合同作为可比样本，并统计：

- 可比合同样本数
- 平均每流程价格
- 中位每流程价格
- 25% / 75% 分位
- 当前每流程买入价
- 当前价相对平均价格的偏差
- 当前价相对中位价格的偏差
- 按可比均价估算的整张 / 整包 BPC 价值
- 蓝图自身潜在价值差

优先使用：

```text
同 Blueprint Type + 同 ME + 同 TE
```

当同 ME / TE 的可比样本不足时，退回：

```text
同 Blueprint Type 的全部 ME / TE 可比合同
```

## 默认“显著低估”门槛

当前默认要求：

```text
可比样本 >= 3
当前每流程价至少比可比平均低 25%
当前每流程价至少比中位价低 10%
按可比平均估算的价值差 >= 10M ISK
```

这些门槛均可通过环境变量调整。

合同市场偶尔存在离谱挂价。样本足够时会先移除非常极端的 IQR 离群报价，再计算平均值；同时用中位数做第二重校验，避免单个高价合同制造假捡漏。

注意：这里衡量的是**当前公开合同挂牌基准**，不是历史真实成交价。

---

# 3. BPC 制造利润：第二条价值参考

BPC 自身明显低估是现在的主信号，制造利润仍然保留。

制造模型：

```text
买 BPC
→ Jita 采购材料
→ Jita 周边低 SCI 高安 NPC 工厂制造
→ Jita 出售成品
```

全成本净利润：

```text
最终净利润
= 成品预计收入
- BPC 合同价格
- Jita 原材料采购成本
- 制造总安装费
- Broker Fee
- 销售税
- 改价成本预留
- 物流成本
```

制造总安装费已经包含 SCI / facility tax / SCC 等工业费用；SCC 只拆分展示，不重复扣除。

制造扫描仍会检查：

- Jita 材料真实卖盘深度
- Jita 成品买盘深度
- 近期成交量
- 批次市场承载能力
- 7 / 30 日 VWAP
- 当前买价偏离
- 买盘容量
- 机会持续性

一张 BPC 可能出现三种情况：

```text
A. 蓝图自身明显低估 + 制造也赚钱      → 最优
B. 蓝图自身明显低估 + 制造暂时一般      → 仍可进 BPC TOP10
C. 蓝图自身无明显折价 + 制造利润很强    → 作为制造型候选补充
```

BPC TOP10 排序中，**自身每流程低估优先级高于纯制造利润**。

---

# 4. 单件 / 多件现货合同捡漏

现货线扫描全服公开 `item_exchange` 合同，把整包合同拆成每种物品和数量，再按 Jita 当前市场深度重新估值。

主要寻找：

- 单件商品错价
- 多件商品整包低估
- 杂包里的隐藏高价值物品
- 买下后可直接砸 Jita 买单仍有利润的合同
- 不能立即兑现，但按挂卖价格仍有明显利润的合同

## A 类：即时买单套利

```text
即时净利润
= Jita 当前买单真实可成交金额
- 销售税
- 合同价格
- 物流预留
```

## B 类：挂单潜在套利

```text
挂单预计净利润
= Jita 当前卖价参考价值
- Broker Fee
- 销售税
- 改价预留
- 合同价格
- 物流预留
```

B 类是估算潜力，不代表立即可兑现。

---

# 5. 全星域风险分层

现货合同和可执行 BPC 价值机会都会解析所在星系。

当前风险等级：

| 等级 | 含义 |
|---|---|
| A1 | 当前联盟 / 显式配置友军势力范围 |
| A2 | Jita 安全路线约 25 跳内高安 |
| B | 其他高安 |
| C | 低安 |
| D | 非友军 00 / 高风险玩家建筑 |

风险等级不修改商品或蓝图本身的价值，只用于风险说明和较小的排序调整。

---

# 6. CACX / 当前联盟区域识别

系统使用配置角色的公开 ESI 角色信息获取当前 `alliance_id`，再结合公开 sovereignty map 判断 00 主权归属。

当前配置角色 ID：

```text
2124493042
```

这只使用公开 ESI，不需要新增 OAuth Scope。

如果合同位于当前角色联盟的主权星系，会自动标记：

```text
A1 联盟势力范围低风险
```

并预留：

```text
DEAL_FRIENDLY_ALLIANCE_IDS
DEAL_FRIENDLY_REGION_IDS
```

用于以后确认蓝盟 / 友军范围后补充。

公开 ESI 不能完整公开联盟外交蓝名单，所以没有明确证据的联盟不会自动假定为友军。

---

# 7. 不可达星系与玩家建筑

现货候选以及 BPC 自身价值候选在推送前都会要求：

```text
有效 system_id
+ 能解析合同位置
+ 从 Jita 存在普通星门最短路线
```

无法满足的合同直接从主榜 / 邮件候选剔除。

玩家建筑如果能通过 EVE Ref Structures 数据解析到星系，可以继续参与；但程序无法保证角色拥有停靠权限，所以接受合同前必须人工确认。

---

# 8. EVE Mail 推送

每轮最终发送两封独立邮件。

## BPC 蓝图捡漏

```text
BPC蓝图捡漏 · TOP10
```

主要显示：

- 蓝图名称
- BPC 张数 / 总流程
- 合同价
- 当前每流程价格
- 可比平均每流程价格
- 中位每流程价格
- 折价幅度
- 可比样本数
- 整包合同市场估值
- 蓝图自身潜在价值差
- 制造净利润 / ROI（如果有）
- 所在星系 / 地点
- 风险等级
- 一键打开合同

## 现货合同捡漏

```text
现货合同捡漏 · TOP10
```

显示合同物品、总价、价值来源、Jita 即时 / 挂卖估值、净利润、ROI、运输预留、地点和风险等级等。

不足 10 个真实合格机会时不会硬凑数量。

---

# 9. 发送前存活复核

邮件发送前会再次通过 ESI 检查候选合同是否仍然存在。

已被买走 / 已失效 / 不可见的候选会剔除，再从后续候选补位，直到 TOP10 或候选耗尽。

---

# 10. 主要输出文件

## BPC 自身价值

```text
results/latest/bpc_value_opportunities.csv
results/latest/bpc_value_all.csv
```

`bpc_value_opportunities.csv` 是显著低估、地点可解析且可达的 BPC 价值主榜。

## BPC 制造

```text
results/latest/ranked_opportunities.csv
results/latest/all_executable_scored.csv
results/latest/product_watchlist.csv
results/latest/excluded.csv
results/latest/meta.json
results/state/opportunity_history.csv
```

## 现货

```text
results/latest/contract_deals.csv
results/latest/contract_deals_all.csv
```

---

# 11. 主要脚本

```text
scanner_source.py
runner.py
```

BPC 制造利润扫描。

```text
bpc_contract_benchmark.py
```

全星域 BPC 每流程合同市场估值、显著折价筛选、位置风险解析，并把估值字段回填到制造榜。

```text
contract_deal_scanner.py
```

全星域单件 / 多件现货合同扫描和风险分层。

```text
filter_reachable_contract_deals.py
```

剔除无法解析或普通星门不可达的现货合同。

```text
send_eve_mail_dual.py
```

分别生成 BPC TOP10 和现货 TOP10 邮件；BPC 候选是“自身价值 + 制造利润”的并集，自身价值优先。

```text
send_eve_mail_fast.py
```

EVE Mail、角色解析和合同存活检查等通用逻辑。

---

# 12. 常用环境变量

## BPC 自身价值

```text
BPC_VALUE_MIN_SAMPLES
BPC_VALUE_MIN_EXACT_SAMPLES
BPC_VALUE_MIN_DISCOUNT
BPC_VALUE_MIN_MEDIAN_DISCOUNT
BPC_VALUE_MIN_SURPLUS
BPC_VALUE_MIN_HOURS_TO_EXPIRE
BPC_VALUE_TOP
```

## BPC 制造

```text
MIN_NET_PROFIT
MIN_NET_ROI
PREFILTER_TOP
PREFILTER_MIN_GROSS_REVENUE
PREFILTER_MIN_ROI
PREFILTER_MAX_OUTPUT_DAYS_30D
ACCOUNTING_LEVEL
HIGHSEC_HAUL_ISK_PER_M3
HIGHSEC_MAX_JUMPS_FROM_JITA
MARKET_BROKER_FEE_RATE
ADV_BROKER_RELATIONS_LEVEL
EXPECTED_RELISTS
```

## 现货 / 联盟风险

```text
DEAL_MIN_CONTRACT_PRICE
DEAL_MIN_PRELIM_EDGE
DEAL_MIN_NET_PROFIT
DEAL_MIN_NET_ROI
DEAL_MIN_LIST_NET_PROFIT
DEAL_MIN_LIST_NET_ROI
DEAL_JITA_NEAR_SECURE_JUMPS
DEAL_LOCATION_PREFILTER_TOP
DEAL_HAUL_BASE_ISK
DEAL_HAUL_ISK_PER_M3_JUMP
DEAL_FRIENDLY_CHARACTER_ID
DEAL_FRIENDLY_ALLIANCE_IDS
DEAL_FRIENDLY_REGION_IDS
```

## 邮件

```text
EVE_MAIL_API_KEY
EVE_MAIL_RECIPIENT_NAME
EVE_MAIL_WORKER_URL
MAIL_MIN_NET_PROFIT
MAIL_MIN_NET_ROI
MAIL_TOP
MAIL_LIVE_POOL
```

---

# 13. 安全与限制

程序只负责：

```text
发现 → 估值 → 风险分类 → 推送
```

实际接受合同、运输、生产和交易由玩家本人操作。

主要限制：

- EVE Ref / ESI 有缓存和快照延迟
- 合同价格可以快速变化
- BPC 可比平均价是公开挂牌价，不是历史成交价
- 稀有 BPC 样本可能很少
- 玩家建筑可能无 Dock 权限
- 低安 / 00 实际风险高度动态
- 现货大体积运输成本只是估算
- 挂单价值不等于立即成交价值

所有机会投入 ISK 前都应在客户端重新确认合同内容、位置、权限和市场状态。
