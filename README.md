# EVE Contract Arbitrage System

一个面向 **EVE Online Tranquility** 的自动化合同套利扫描系统。

当前项目包含两条彼此独立的主线：

1. **BPC 蓝图制造捡漏**：扫描公开蓝图复制品合同，计算从买入 BPC、采购材料、制造到最终出售的全成本净利润。
2. **单件 / 多件现货合同捡漏**：扫描公开 `item_exchange` 合同，把合同内所有物品拆开按 Jita 市场重新估值，寻找整包错价、隐藏高价值物品和可立即兑现的套利机会。

两套引擎独立排名、独立复核、独立发送 EVE 游戏邮件，每轮各最多推送 **TOP 10**。

---

## 自动运行

GitHub Actions 默认每天运行两次：

- 北京时间 **08:35**
- 北京时间 **20:35**

对应 UTC：

```text
35 0,12 * * *
```

也支持在 GitHub Actions 页面手动触发。

完整流程：

```text
公开合同 / 市场数据
        ↓
BPC 制造扫描器
        ↓
现货合同扫描器
        ↓
BPC 合同市场自身估值
        ↓
生成一键 EVE 合同链接
        ↓
发送前 ESI 合同存活复核
        ↓
两封独立 EVE Mail
        ↓
保存 CSV / 历史结果
```

---

# 1. BPC 蓝图制造捡漏

## 核心逻辑

扫描全服公开 BPC 合同，寻找：

```text
买 BPC
→ Jita 采购材料
→ 高安低 SCI NPC 工厂制造
→ 在 Jita 出售成品
```

在计入全部主要费用后仍然有利润的机会。

## 全成本利润口径

当前净利润模型：

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

其中：

```text
制造总安装费
= SCI / system cost index 相关成本
+ facility tax
+ SCC surcharge
+ 其他 EVE 工业安装费用
```

注意：**SCC 已包含在制造总安装费中，只拆分展示，不重复扣除。**

## 快速漏斗

为了降低全服扫描时间，BPC 引擎先进行廉价粗筛，再进行精算。

主要粗筛条件包括：

- 公开 `item_exchange` 合同
- 交付物为可制造 BPC
- 排除需要买方提供额外物品的合同
- 排除不适合自动执行的真旗舰 / 超级旗舰项目
- 优先处理单一成品类型
- 批次价值达到最低门槛
- 粗利润和粗 ROI 达到门槛
- Jita 买盘能够吸收一批产量
- 批次产量不能明显超过近期市场成交能力

精算阶段再计算：

- Jita 材料真实卖盘深度
- 当前 Jita 成品买盘深度
- 低 SCI 工厂制造费用
- Broker / Sales Tax / Relist Reserve
- 市场成交量
- 7 / 30 日 VWAP
- 当前买价相对历史价格的偏差
- 当前买盘可承载多少份同类合同
- 机会持续性
- 综合评分

---

# 2. BPC 自身合同市场价值

部分特殊、流程类或稀有 BPC **没有正常 Jita 市场价格**，因此只看制造利润可能低估蓝图本身的价值。

系统会对最终 BPC 候选额外进行合同市场估值。

对于同一种 BPC，统计全服公开合同中的：

- 每流程价格（ISK / run）
- 平均每流程价格
- 中位每流程价格
- 可比合同样本数
- 当前合同每流程买入价
- 当前价格相对市场平均 / 中位的偏差
- 按合同市场价格估算的整张 / 整包 BPC 价值
- 蓝图自身潜在价值差

优先比较：

```text
同 Blueprint Type + 同 ME + 同 TE
```

如果同 ME / TE 样本不足，再退回：

```text
同 Blueprint Type 的全部 BPC 合同
```

同时保留 **平均值 + 中位数**，避免极端挂单把平均价格严重拉高。

因此一个 BPC 机会现在有两套价值判断：

```text
A. 买来制造是否赚钱
B. 蓝图本身在合同市场是否被低估
```

---

# 3. 单件 / 多件现货合同捡漏

现货引擎扫描公开 `item_exchange` 合同，不要求合同里只有一种物品。

系统会把多件合同拆成：

```text
物品 A × 数量
物品 B × 数量
物品 C × 数量
...
```

然后逐件读取 Jita 当前市场深度，重新计算整个合同包的真实价值。

这主要用于发现：

- 单件商品明显错价
- 多件商品整包低估
- 某个不起眼的高价值物品隐藏在杂包里
- 卖家根据错误总估值定价
- 买下整包后直接卖给 Jita 买单仍然赚钱的机会

## A 类：即时买单套利

优先级最高。

```text
即时净利润
= Jita 当前买单真实可成交金额
- 销售税
- 合同价格
- 物流成本预留
```

只有当前买盘实际能够吃下相应数量时，价值才会计入。

## B 类：挂单潜在套利

如果立即砸买单利润不足，但按当前市场卖价挂单仍有明显空间，则作为第二级机会。

```text
挂单预计净利润
= Jita 当前卖价参考价值
- Broker Fee
- 销售税
- 改价成本预留
- 合同价格
- 物流成本预留
```

B 类不等于即时可兑现利润，因此邮件中会明确标记。

---

# 4. 全星域风险分层

现货合同数据源是 **Tranquility 全服公开合同**。

扫描器不再只关注 Jita 周边高安，而是按照合同所在地进行风险分层。

当前风险等级：

| 等级 | 含义 |
|---|---|
| A1 | 当前联盟 / 配置友军势力范围，联盟低风险 |
| A2 | Jita 安全路线约 25 跳内高安 |
| B | 其他高安 |
| C | 低安，高风险 |
| D | 非友军 00 / 无法确认的玩家建筑，高风险 |

风险等级 **不会修改商品本身的市场价值**，但会影响推荐排序，并在邮件中明确展示。

---

# 5. CACX / FRT 联盟区域识别

项目当前使用公开 ESI 信息读取配置角色的当前联盟，然后结合公开 sovereignty map 判断 00 主权归属。

当前配置角色：

```text
MikeChong
```

其角色 ID 仅用于公开角色 / 联盟查询，不需要新增 OAuth Scope。

如果合同所在 00 星系属于当前角色所在联盟的主权，则自动标记：

```text
A1 联盟低风险
```

另外预留：

```text
DEAL_FRIENDLY_ALLIANCE_IDS
DEAL_FRIENDLY_REGION_IDS
```

用于以后确认蓝盟或长期友军区域后手工加入。

注意：公开 ESI **不能完整公开联盟外交蓝名单**，因此“联盟低风险”默认只保证当前联盟自身主权以及显式配置的友军范围。

---

# 6. 玩家建筑

公开合同可能位于玩家建筑。

现货扫描器会尝试通过 EVE Ref Structures 数据解析：

- structure id
- system id
- region id
- 建筑名称

如果能够解析，则继续参与全星域风险判断。

如果无法解析，不直接假定安全，而是标记为：

```text
D 玩家建筑未知风险
```

实际接受合同前仍需要确认：

- 是否有 Dock 权限
- 是否有资产安全风险
- 建筑是否即将失效 / 被摧毁
- 运输路线是否可执行

---

# 7. EVE Mail 推送

每轮扫描最终发送 **两封独立邮件**。

## 蓝图制造捡漏

```text
蓝图制造捡漏 · TOP10
```

内容包括：

- 成品
- BPC 合同价
- 材料成本
- 制造费用
- SCC 明细
- Broker
- 销售税
- 改价预留
- 物流
- 最终净利润
- 最终净 ROI
- 买盘容量
- BPC 每流程市场基准
- 当前每流程价格偏差
- BPC 自身估值
- 一键打开合同

## 现货合同捡漏

```text
现货合同捡漏 · TOP10
```

内容包括：

- 合同内物品
- 合同总价
- 主要价值来源
- Jita 即时买单价值
- Jita 挂卖参考价值
- 净利润
- 净 ROI
- 买盘覆盖
- 物流预留
- 所在星系 / 空间站 / 玩家建筑
- Security
- 距 Jita 跳数
- 风险等级
- 一键打开合同

如果某一类只有 3 个合格机会，则只发送 3 个，不使用低质量机会硬凑 TOP10。

---

# 8. 发送前合同存活复核

扫描数据本身存在缓存与快照延迟。

因此在真正发送 EVE Mail 之前，会再次通过 ESI 对候选合同做存活检查。

如果排名靠前的合同已经被其他玩家买走或不可见：

```text
自动剔除
→ 从后续候选补位
→ 直到达到 TOP10 或没有更多合格合同
```

这只能减少过期合同，不能完全消除 ESI 缓存和多人竞争造成的抢单失败。

---

# 9. 当前主要输出文件

## BPC

```text
results/latest/ranked_opportunities.csv
results/latest/all_executable_scored.csv
results/latest/product_watchlist.csv
results/latest/excluded.csv
results/latest/meta.json
results/state/opportunity_history.csv
```

## 现货合同

```text
results/latest/contract_deals.csv
results/latest/contract_deals_all.csv
```

其中：

```text
ranked_opportunities.csv
contract_deals.csv
```

是最值得直接查看的两个主榜。

---

# 10. 主要脚本

```text
runner.py
```

加载并运行 BPC 快速扫描器。

```text
scanner_source.py
```

BPC 制造套利核心逻辑。

```text
contract_deal_scanner.py
```

全星域单件 / 多件现货合同套利扫描器。

```text
bpc_contract_value.py
```

计算 BPC 合同市场每流程价格和蓝图自身估值。

```text
send_eve_mail_dual.py
```

生成并分别发送 BPC TOP10 和现货 TOP10 邮件。

```text
send_eve_mail_fast.py
```

包含 EVE Mail、角色解析和合同存活检查等通用逻辑。

```text
add_action_links.py
```

为结果增加可在 EVE 客户端中打开的合同 / 市场链接。

---

# 11. Cloudflare Worker

项目配套一个 Cloudflare Worker，主要承担：

- EVE SSO
- ESI Token 相关服务
- 发送 EVE Mail
- 合同跳转链接
- 市场物品跳转链接

扫描和套利判断主要在 GitHub Actions / Python 中完成。

也就是说：

```text
GitHub Actions = 扫描 + 计算 + 排名
Cloudflare Worker = EVE 授权 + 邮件 + 跳转
```

---

# 12. 常用环境变量

## BPC

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

## 现货合同

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

本项目只使用公开市场 / 合同数据和官方 ESI 允许的接口。

程序负责：

```text
发现机会
→ 计算
→ 风险分类
→ 推送
```

实际接受合同、运输、生产和交易仍由玩家本人操作。

不要使用输入自动化、鼠标宏或其他违反 EVE Online 第三方工具政策的方式自动接受合同或自动进行游戏操作。

此外：

- 市场价格可能快速变化
- EVE Ref / ESI 存在缓存
- 玩家建筑可能无权限停靠
- 低安 / 00 风险高度动态
- 大体积货物的真实运输成本可能远高于简单估算
- 挂单参考价值不等于即时成交价值
- BPC 合同市场平均价只代表当前公开报价，不代表真实成交价

所有机会在实际投入 ISK 前仍应在客户端做最终确认。

---

## 当前目标

项目目标不是寻找“理论利润最高”的合同，而是寻找：

```text
真实可执行
+ 全成本后仍赚钱
+ 流动性可承受
+ 风险可以识别
+ 能及时收到并抢到
```

的 EVE 合同套利机会。
