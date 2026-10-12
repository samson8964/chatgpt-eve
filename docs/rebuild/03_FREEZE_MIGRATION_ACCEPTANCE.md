# EVE 旧版封存、重建切换与验收计划 v0.1（Draft）
> **设计冻结与生产停机不是一回事。** 本文只用于计划；未执行归档标签/停用 Cron、Secrets 迁移、生产切换。

## 0. 决策：原仓库保留，业务代码在独立命名空间完全重写
**原因：** 已有 GitHub Actions Secrets、Cloudflare Worker/SSO、角色 ESI 授权、已知可访问建筑 API、现成工作台连通。迁到新 GitHub 仓库不能自动复制 Secrets，也容易要求再次登录/授权。推荐在 samson8964/chatgpt-eve 原仓库：
- 先创建不可变 Git tag（预案：legacy-v3-final-YYYYMMDD-SHA）与只读 archive branch；导出历史事故 fixture 与需要保存的原始数据索引，记录 checksum；
- 在独立 rebuild/* 分支及全新 **next/** 下创建新项目；不 import 旧 runner/scanner/mail/state/policy 引擎，不沿用旧 main CSV 作为生产数据库；
- 旧代码仅作离线比较基准。现有 Cloudflare Worker 在过渡期被视为已授权的**外部服务接口**；新内核不得复制旧业务代码。若要最终连 Worker 调度/API 内部代码全部替换，应另开接口兼容的独立 Worker，并单独验证 SSO，不在第一阶段破坏可用授权；
- 待纯新系统验收后再按用户明确批准改变 main 生产入口与部署触发；历史 tag/archive 不能删除，保留回滚入口。

## 1. 资产清单与不动边界
| 资产类型 | 保留方式与核验 | 冻结原则 |
|---|---|---|
| GitHub repo / Secrets / workflow permissions | 同仓库新代码继承 Secrets *引用能力*（不读取明文），生产和影子单独配置权限 | 不改/不在文档输出真实 token、client secret、密码 |
| Cloudflare 账户 / Worker / Cron / KV | 导出非敏感 wrangler 绑定和路由清单、线上 health、Cron，备份现有 Worker 部署版本 | 不先停旧 Worker；新增持久数据库绑定须单独验收 |
| EVE SSO 身份与角色授权 | LadyGuaGua 发信；MikeChong、LadyBaBa 采购及权限；按实际可用 scope/expiry/ACL 清点 | 不重新授权正常可用的角色；缺权限明确报错、人工操作才补授权 |
| ESI / EVE Ref / NPC/建筑市场/公开合同 | 保存端点、响应 schema、分页、ETag/缓存、限流策略与 fixture；4-H/C-J/O4T 的每个建筑访问逐一实测 | 不因源码重写就改变已证明可用的 source id、角色 profile |
| 正式经济约束 | Approved Roadmap + Airtable Decisions + decision hashes 形成锁定 policy registry | 净利>=50M、非 BPC >=2000 ISK/m³、BPC/高价值特殊门槛不隐式变更 |
| 旧数据与通知历史 | 备份 mail_last/mail_seen/gmail_seen、fingerprints、candidate_pool、run 日志、ESI 快照与相关 commits；记录来源与完整性 | 不清空历史，不直接将历史快照标为「当前 live」 |
| AI Workbench | GitHub 代码真源；Notion 说明；Airtable 项目/运行/机会概况；Drive 证据文件 | 只同步可验证结论，不把 Draft 误当 Approved |

> 必须单独决议：Issue #27 涉及 BPC 已批准严格政策与某版适配器的执行政策差异。新系统的投产决策不得默默采用更宽松的四关。

## 2. 提案执行阶段、成果、退出条件
| 阶段 | 主要内容 | 通过条件 |
|---|---|---|
| R0 只读封存 | 标记 legacy tag/archive；导出失败案例、既有密钥名称但不导出密钥；锁定版本、已批准业务策略 | 新旧代码/Secret/Worker/状态完整盘点，能够基于 tag 复原旧行为 |
| R1 契约和架构 | 共同定义 RawSnapshot、ExecutionProof、OpportunityID、NotificationEvent、TradeEvent；明确生产/影子边界 | Schema 合约测试和示例 fixture 通过；策略歧义清单经用户决议 |
| R2 新底座 | 新 adapter + 数据库 + 运行日志 + config profile + scheduler lane locks；只做 read-only | 历史和并发重跑结果确定；失效 ESI/ACL/重启/跨轮状态可重放 |
| R3 最小全链路 | 公开现金合同 + 一个市场来源（卖单→Jita买单）：发现→逐档验证→Gate→Outbox dry-run→模拟采购/出售记账 | 真实采集但禁止邮件；一条可溯源机会完全走通；没有订单级身份则不能宣称新市场机会 |
| R4 扩源与模型 | 4-H/C-J/O4T/艾玛/多迪谢、BPC/高价值；每类独立 adapter、共享成交引擎/Gate/Outbox | 分来源健康指标、旧事故回放、账户权限对照，BPC 策略与制造费用校准 |
| R5 历史回放/影子 | 读取至少 7 天可用历史快照，重放典型事故；新系统在现有生产旁仅**只读 shadow**，收集连续多轮差异 | 不重复通知、不新发真实信；质量、召回、成本假设和运行时间满足验收矩阵 |
| R6 灰度切换 | 人工批准后只选择一条渠道转正式发信；独立切换开关与一键回滚；其他旧通道维持 | 连续运行状态和消息 ID 能审计，出现异常直接关新 outbox，不丢状态 |
| R7 全量切换 | 逐一迁移来源与角色，旧生产扫描/邮件调度停止，但历史只读保留 | 新版 7 天稳定窗口满足硬性指标，P3 真实利润审计数据链路可追溯 |

**关键约束：** R0 的「代码冻结」仅指停止对 V2/V3 加新功能；针对重大生产错误的必要安全修复仍可按既有正式流程处理。停用旧调度需要另外明确的切换批准，不因为建 Draft 立刻发生。

## 3. 技术与业务验收矩阵（门槛提案）
### A. 不允许妥协的硬门
1. 合同相同 contract_id 经过 2→1→2 排名波动、相隔多天、重新启动、两个航道并发，**首次通知事件数 = 1**；市场相同 instance_key 同理。
2. 同一 type_id 的真实**不同新订单实例**经充分撮合证明仍满足 Gate 时，有被作为新实例识别的能力；不能只用 type_id 永久拉黑，也不能只用价格涨跌伪造「新单」。
3. 订单深度不完整/体积未知/权限 403/过期报价/缺税费版本/未知厂址时，正式现金 MAIL = 0，原因可追踪。
4. 买卖方向必须正确：采购来源价为源卖单，兑现目的价为真实买单，按份额分档、税费和可成交数量算净利；压力去最佳档后利润必须有效且正。
5. 所有来源共同使用**唯一正式 Mail Gate**。任何 scanner、booster、shadow、push job 不能绕开 Gate 触发真实提醒。
6. 扫描中断/SMTP失败/ESI 520/超时：不遗失 pending；外部可能已发出的 uncertain 记录须隔离人工处理；不得把「成功运行」等同「成功投递」。
7. 任意 opportunity 可按 run_id→snapshot/order_ids→proof→policy→outbox→delivery→人工成交回执→实现利润追溯；不能追溯时标记 UNATTRIBUTED，不能自动算正利润。
8. GitHub main 不再按每轮扫描提交高频机会状态；存储灾备和快照 checksum 可恢复。

### B. 连续运行与质量指标
- 最近 7 天真实快照有多少可回放先审计完整性；覆盖不足要补 fixture、不能用假数据伪称历史验证通过。
- 至少 **72 小时影子运行**（建议之后观察 7 天），覆盖公开合同、市场、BPC 独立调度。重点核查稳定执行、锁、跳过拥塞、空数据和外部接口降级。
- 重复通知：历史回放对 same instance = 0；在 shadow 应无真实邮件。新订单实例漏报、假机会误报必须人工核对有代表性的样本，不能只看「0 重复」。
- 每条航道的扫描量、召回量、深审量、MAIL 量、新实例量、重算量、错误率、订单年龄、运行时长可按 run 查询。
- 推送后再检查 live depth 和可兑现净利润变化；无已实现成交时禁止宣传已证明年化收益或稳定月利润。
- 新版异常触发回滚：错误正式邮件、来源故障被标为 LIVE、连续状态写入失败、运行造成真实重复、Gate 意外放宽。可立即暂停新 outbox，不应同时关闭全部旧档案或删除数据库。

## 4. 最小事故回放包与真值要求
- 历史公共合同旧 ID：236897299、236664299（出现过重复推送）；作为同合同跨轮、TTL 与迁移去重样本，不代表现仍可交易。
- C-J 市场重复类型、旧 Gmail 6h 再提醒、利润恶化和 TOP 重入场景。
- 10/10 C-J 403 与 O4T shadow 绿灯但无可读取订单案例。
- 10/12 PR #34 未持久化候选状态、PR #35 TOP 2→1→2；三角色游戏内邮件 ESI 520/失败保存状态测试。
- BPC 制造订单簿深度不全、工厂运输/税务、远端与 Jita 四关冲突场景。
- 仓库大量 data commits/并行状态提交与误导 Airtable Running 的恢复场景。
每个 fixture 明确 source commit 或 run、样本时间、输入哈希、人工确认的预期行为；属于**错误重演**还是**可被接受的策略变化**需要标注。

## 5. 数据迁移、切换与回滚操作协议
1. 旧数据全量保存为只读档案，制作按 channel+recipient/contract_id、市场 type/order 置信度的迁移映射；状态缺失不得假装从未提醒。
2. 首次切换新系统时按照迁移的 seen baseline 抑制旧 ID 全量重发。缺 order_id 的历史市场状态作为 REVIEW，不把全体历史商品永久禁止。
3. 切换以**通知权限**为最终开关：Shadow 不带可用发信 credential 或强制 EMAIL_DRY_RUN；R6 审批后只授予选定 lane 的独立发信权限。
4. 失败回滚要保存新系统已产生的通知 Outbox/账本，恢复旧版服务前导入对应 seen baseline；否则滚回旧版可能一次性重发大量消息。
5. 旧系统主代码、Cloudflare OAuth/KV 数据、历史结果文件保留到正式验收后至少一个约定的回滚窗口；不得先删除生产凭据或数据。
6. 每次阶段变更写 ADR (Architecture Decision Record)、Git commit SHA、Airtable 运行与决策、Notion 人类说明，版本状态为 Draft/Approved/Deployed/Verified 四层，不能混用。
7. 新服务如采用 D1/对象存储，新增绑定只在新环境配置。保持旧的 ESI/Worker endpoint、角色 OAuth scopes、现有合法 key 不变；权限不足才按人工授权边界处理。

## 6. 重建决定前应答复的三项设计风险（无需现在重复提供凭据）
1. **V2/V3 是否继续正式提醒直到灰度完成？** 默认继续；若旧信号已严重误导用户，可单独申请「只暂停旧通知、保留只读扫描」。
2. **新状态数据库具体选型：Cloudflare D1 还是单机 SQLite？** 核验 Cloudflare 配额、部署权限、跨 Actions 并发、灾备与性能；不预先假定已有 D1。
3. **BPC 策略冲突以何者为准？** 默认依已批准严格规则，不放宽；Issue #27 必须先经决策闭环后才能在新版正式发 BPC MAIL。

**版本状态：Draft，仅架构和归档资料。任何自动买入/资产变更仍不在授权范围内。**