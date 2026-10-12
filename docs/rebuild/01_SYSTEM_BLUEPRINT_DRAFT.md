# EVE 捡漏系统重建蓝图 v0.1（Draft，未批准）
> 独立设计文件。此文件不代表 V4 已部署、不修改生产规则，也不代表旧版已停止。

## A. 为什么重建，以及不做什么
**北极星：** 在可信的来源数据、真实可执行的买/卖单深度、可复核的成本与风险下发现新套利机会；通过独立人工交易与后续 ESI 证据确认真实利润，形成持续优化的低劳动闭环。
- 不以扫描次数、候选数量、邮件数量、GitHub CI 绿色为业务成功。
- 旧 V2/V3 的算法与流程代码仅供测试对照、错误档案、复盘和必要回滚；重建时不复用其隐含状态/发信/排序副作用，不复制粘贴有缺陷的架构。
- 当前生产系统在正式切换前不被这个 Draft 停用；本计划不授权删除代码、关闭 Cron、重置 SSO、清空历史去重或自动买卖。
- 不为「重建」要求用户重新登录已有可用 ESI、重新填 API Key、重新创建已有 GitHub Secrets。只有新增的存储/服务绑定需要单独配置和验证。

## B. 核心原则与策略
1. **数据事实和决策彻底分离。** 原始 ESI/Ref/API 快照保留时间、区域、订单 ID、访问角色与请求结果；经济模型计算可追溯的 ExecutionProof；政策引擎单独判断 RESEARCH/WATCH/SAFE/MAIL。
2. **可执行优先。** 买入端按照真实卖单、卖出端按照真实买单逐档撮合，计入数量、滑点、税、运输、费用、压力测试与失效/权限。
3. **双层机会身份。** 同一市场策略的长期品类 family 与由真实买卖订单 ID + 来源/目的地/数量档构成的 instance 必须区分；同一订单的价格刷新是同一个 instance 的版本变化，而不是全新机会。合同按 ESI contract_id 作为首选唯一身份。
4. **存储即历史。** 每轮 run / source health / snapshot / calculation / gate / alert / user action 形成增量不可变事件；SQLite/D1 一类事务型持久存储负责状态，GitHub 不再充当每 15 分钟的业务数据库。
5. **单一通知出口。** 所有策略最终只写入规范化机会和统一 Outbox；游戏内邮件、Gmail 分别分配 delivery_id，任何扫描器都不直接发信或维护另一套自定义 last-TOP。
6. **严格失败隔离。** 数据缺失、订单深度不完整、未验证建筑访问、未知体积、失效来源、未识别经济参数时 fail-closed；一个通道故障不能污染其它通道，也不能用上轮成功文件伪装本轮数据。
7. **策略版本固定。** 每次 Proof 和通知附 policy_version + assumptions_profile_id + source_snapshot_ids + run_id；未经用户确认不暗改利润、ROI、密度、角色、税运假设。
8. **人执行交易，系统留痕。** 不自动签合同/买入/转移资产/制造/卖出；扫描推荐不等于已执行。

## C. 推荐的数据与运行架构
~~~mermaid
flowchart TD
  A["Cloudflare Cron / 手动触发"] --> B["调度器：单航道排他锁、跳过拥塞、任务ID"]
  B --> C["GitHub Actions 运行器 / 未来本地Runner"]
  C --> D["数据适配器：ESI/Ref/结构Worker/角色权限"]
  D --> E["不可变 RawSnapshot + SourceHealth（时间、来源、订单ID）"]
  E --> F["发现引擎：广发现 + 候选轮换"]
  F --> G["验证引擎：订单逐档兑现 / 制造BOM / 物流 / 压力情景"]
  G --> H["Versioned ExecutionProof"]
  H --> I{"统一 Policy Gate"}
  I -->|"RESEARCH/WATCH"| J["研究记录，绝不自动当正式现金机会"]
  I -->|"SAFE/MAIL"| K["机会注册表：family/instance/version/lifecycle"]
  K --> L["Outbox：幂等身份、送达状态、频控、人工审核"]
  L --> M["游戏邮件 / Gmail"]
  K --> N["人工交易回执 + ESI Wallet/Orders/Contracts/Assets"]
  N --> O["真实持仓与已实现利润审计"]
  O --> P["Airtable 指标 / Notion 决策 / Drive 证据"]
  P --> Q["回测、版本评审、用户批准后参数变更"]
  Q -.-> I
~~~

### 推荐责任分层（新代码独立命名空间）
- **adapters/**：公开合同、NPC 市场、建筑市场、Jita 买/卖单、EVE Ref、工业活动、角色审计。一个 API 一个带断言的数据契约与错误分类；鉴权交由现有 Worker/Secrets。
- **schemas/**：源快照、订单簿、合同、Blueprint、ExecutionProof、GateDecision、Opportunity、OutboxEvent、TradeEvent，全部使用带版本的严格类型。
- **discovery/**：按收益、ROI、新合同、价格改变、冷门/探索等多样性召回，只产候选、不决定最终 MAIL。
- **valuation/**：现金合同 FULL / PARTIAL、物物交换、市场跨站套利、制造 BPC、高价值资产包；使用共享订单簿撮合、费用/运输、压力测试组件。
- **policy/**：纯函数规则；统一最终 PolicyEngine；不同策略可以有独立资格规则，但不能各自绕过最后的 Gate。
- **store/**：扫描运行、快照索引、机会实例、审核结果、告警 outbox、人工动作、仓位、收益。生产业务事实不提交进 GitHub main。
- **notify/**：通知编排、收件人、消息版式、渠道状态、发送审计；worker 发信层不参与机会筛选。
- **reconciliation/**：三角色资金/资产/合同订单与成本批次关联，人工回执与可证实 ESI 事件双向核对。
- **reports/**：实时仪表盘、漏斗/失败原因、新机会比例、实际净利润；向 Airtable/Notion 输出摘要而非复制全部原始数据。

## D. 机会身份、生命周期与通知去重
**两种 identity：**
- ContractFamily = route + start_location + contract_type；ContractInstance = ESI contract_id；同合同重新计算、改变 TOP 排名不得再次算「新合同」。
- MarketFamily = source_structure/station + destination_market + strategy + type_id；MarketInstance = 经过验证的 source_sell_order_ids + destination_buy_order_ids + execution quantity band 的规范化指纹（同一组真实可成交订单）；QuoteVersion = snapshot hash + 可执行数量、净利/ROI、订单深度。无 order_id 只能进入 WATCH/REVIEW，不允许凭 type_id 变化宣称「发现新订单」。
**状态：** DISCOVERED → VALIDATING → WATCH / ACTIONABLE / REJECTED → ALERT_PENDING → ALERTED → USER_ACCEPTED / IGNORED → PURCHASED → IN_TRANSIT / IN_PRODUCTION → SOLD / HELD / EXPIRED → RECONCILED。
- 保留 REJECTED 原因与每次计算快照；不同运行轮次更新版本，不覆写首见时间。
- Outbox 在数据库内建立唯一键 (instance_key, channel, alert_kind, policy_version)；正式新机会只生成一次首次通知事件。二次提醒（如利润改善）必须有明确规则、可验证订单变化与用户认可。
- 外部 ESI/SMTP 不支持我们控制的端到端事务。出现「邮件可能已送达但响应超时」时设为 DELIVERY_UNCERTAIN，不盲目重试以免双发；通过下一轮送达查询/人工复核或防重复窗口决定处理。不可许诺不可能的精确一次外部投递。
- 历史游戏邮件/Gmail 两套旧账本转换为 migration baseline，保留来源、完整性、不确定性；禁止空账本上线后补发数百条旧机会。

## E. 固定的正式经济与运营约束（来自 Approved Roadmap，重建期间冻结）
| 规则 | 当前正式基线 | 备注 |
|---|---|---|
| 普通正式机会净利润 | 已验证净利润 >= 50,000,000 ISK | 初筛阈值可更低，不等于正式提醒阈值 |
| 非 BPC 利润密度 | >= 2,000 ISK/m³ | 未知/无穷/非正体积必须拒绝自动 MAIL |
| 普通执行风控 | SAFE，真实深度、压力利润正、位置与访问可信 | 计算输入可溯源，经济参数版本化 |
| BPC 已批准口径 | 远端 V2 SAFE，远端 >=100M / ROI>=15% / stress>=50M；另 Jita 制造 >=50M / ROI>=10% / stress>0，材料及成品深度完整 | **生产适配器曾与批准口径冲突，见 Issue #27；上线前强制决议，不悄悄选一方** |
| 大合同 | >5B 单独分级，只有 5–8B ACTIONABLE 且 SAFE、净利>=500M、ROI>=10%、压力盈利可自动提醒 | 8–20B WATCH、>20B RESEARCH，不自动交易 |
| 角色分工 | MikeChong / LadyBaBa 采购；LadyGuaGua 集中销售与现有游戏邮件发送授权 | 三角色成本批次必须关联；角色间内部转移不等于盈亏 |
| 监测区域 | 4-H、C-J6MT、O4T-Z5 / SummerHall、Jita、Amarr、Dodixie 及已批准范围 | 通过能力清单逐项核验权限和产出，不假设 ACL 生效 |
| 调度基础 | 现 Cloudflare fast 15m 尝试、BPC 每3h、O4T 每2h | 只是当前资源和调度配置；新系统可不改 Cron，但需尊重单轮耗时与航道锁 |
| 行为边界 | 不自动买入/接受合同、转移资产或出售 | 一切资金操作人工决定 |

## F. 数据库与观测的最小实体
- **scan_runs**: run_id, lane, code_sha, config_hash, started/finished, outcome, stages, duration, previous-run link。
- **source_snapshots**: snapshot_id, source, acquired_at, expires_at, access_profile, fetch outcome, content_digest, object store ref。
- **opportunity_families / opportunity_instances / proof_versions**: family_key, instance_key, identity_confidence, raw_snapshot_ids, proof JSON, gate status/version, reason, first_seen, latest_seen, expires_at。
- **notification_outbox / delivery_attempts**: identity key, user, channel, status, attempt_id, sent_at, external mail_id, uncertain state, last_error。
- **manual_receipts / execution_events / positions / realized_pnl**: buy/transfer/production/sell reconciliation evidence; cost lot, fees, sold_qty, held_qty, unmatched_amount, human_verified flag。
- **policy_profiles / audit_events**: approved rules, change request, reviewer, effective date, code SHA, supersedes。
**存储建议：** 用现有 Cloudflare 技术栈的 D1 作为首选评估方案（新增数据库/绑定需要配置，但不改变已有 ESI/SSO Secrets）；只允许一个数据库写入口管理幂等和序列化。可用独立本地/云主机 SQLite 作为对比方案；先完成失效恢复/并发写入/备份验收再选型，不能只因免费就仓促确定。
**控制面：** GitHub 是代码/PR/测试唯一真源；D1 等事务数据库存完整事实；Airtable 显示项目、运行、机会摘要、决策与利润 KPI；Notion 写清已批准策略与故障档案；Drive 存详细样本、审计报告和导出。任何服务都不以手工复制为唯一同步机制。

## G. 范围顺序（先小而完整，再扩扫描）
**首个纵向 MVP：** 公开 item-exchange 现金合同 + 一个可访问来源的市场卖单→Jita买单。重点做从原始订单到真实通知和成交归因的全链路，保留 FULL/PARTIAL 区分，涵盖状态跨轮持久化与订单级去重。
**第二批：** 4-H/C-J/O4T 的独立建筑市场/合同适配器、反向套利；授权失败可观察且不误报。
**第三批：** BPC 严格制造模型与制造场地/物流/技能账户；高价值多件合同独立资本门槛。
**后续研究：** 保守挂卖、蓝图价值、药品、压缩气体、ESS 等若无正式执行现金证据只入 WATCH/RESEARCH；不得混入首个 MVP 正式通知。

## H. 三条不可违反的工程边界
1. 新旧代码、旧数据状态和新数据库严格隔离。新系统在影子期禁止真实发信/交易。旧生产直到用户批准切换继续按现状运行或另行明确暂停。
2. Push/PR 只跑纯测试、离线回放或 shadow，不允许任何可以触发 EVE/Gmail 真邮件的副作用。所有生产执行只能由授权调度/人工审批入口触发。
3. 每一次“已修复”必须提供：失败证据 → 根因 → 不变式 → 单元/集成测试 → 历史回放 → 影子实测 → 正式切换 → 生产收据。绿色 CI 不代表实际生意可靠。

**状态：设计 Draft；等待评审与批准。**