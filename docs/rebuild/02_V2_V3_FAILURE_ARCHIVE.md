# V2 / V3 历史错误、失败模式与重建约束档案 v0.1
> 本档案保留教训，**不把历史问题一律称作今天仍然存在**。分类：CONFIRMED=有源码/日志证据；HISTORICAL=历史发生过、后来可能修复；UNRESOLVED=目前代码/治理仍有未闭环问题；REQUIRES_RECHECK=旧审计的风险判断，重建前应回测。禁止凭绿色 CI 将其改为 CLOSED。

## 证据入口与状态口径
- 源码真源：https://github.com/samson8964/chatgpt-eve
- 正式规则：https://github.com/samson8964/chatgpt-eve/blob/main/docs/ROADMAP_GOVERNANCE.md
- 市场身份/风险遗留：https://github.com/samson8964/chatgpt-eve/issues/33
- 调度/陈旧数据：https://github.com/samson8964/chatgpt-eve/issues/26
- BPC 规则冲突/跨角色审计：https://github.com/samson8964/chatgpt-eve/issues/27
- 邮件机制修改：PR #30、#34、#35（不是无条件成功验收）
- AI 工作台原始历史：https://app.notion.com/p/3e4925dd4c6381869b83e0eee9bc765c
- 每条问题都需要：最小复现输入、预期/实际输出、触发条件、影响、检测指标、修复决策、版本/证据、归档状态。后续应将表格转为机器可读 failure_cases JSONL 和 fixture 数据集。

## A. V2 与早期扫描/估值系统
| ID | 故障/风险与当前口径 | 经验与新版强制约束 | 证据 |
|---|---|---|---|
| V2-01 | 多件、普通合同、V2、V3 等引擎反复发现同一合同；功能重叠。**HISTORICAL** | 合同实例仅有一个 canonical ID 与一条机会生命周期；不同估值出口是同一实例的不同 proof，不允许多个发信器重复派发 | V3 重构 2026-10-07 文档、旧 Notion |
| V2-02 | 用 Jita 卖价、历史 VWAP 或估计价值当即时可兑现买盘，容易出现纸面利润。**HISTORICAL/RECHECK** | 即时兑现必须逐档真实买单成交；挂卖估值只能 WATCH，不得自动冒充 CASH SAFE | 已批准路线图，旧审计 |
| V2-03 | 税率假定 Accounting 5；真实卖出角色技能未知时高估净利润。**HISTORICAL/RECHECK** | 真实 seller_profile 与税费版本化；技能不明时保守拒绝自动信号；禁止隐式满技能 | Notion 2026-09-26 审计；旧 high-value workflow 明示 ACCOUNTING_LEVEL=5 |
| V2-04 | BPC 远端低 SCI 工厂估值，却未包含真实材料/成品运输的旧审计问题。**REQUIRES_RECHECK** | 单一工厂场景必须完成材料采购、安装、税费、物流、产出兑现闭环；Jita 保守基线独立校验 | Notion 2026-09-27 审计 |
| V2-05 | stress_complete 不一致、材料深度不足时保守成本反而可能被低估。**REQUIRES_RECHECK** | 压力情景必须量与价完整；任何一侧缺深度直接降级，测试去掉最佳档与断单 | 旧审计；P0 技术债 |
| V2-06 | 部分药品/制造机会以历史 VWAP、平均预留替代真实费用导致假利润风险。**REQUIRES_RECHECK** | 研究价差与可执行制造套利完全分离，制造开销缺失不进入自动邮件 | Notion 2026-09-27 药品制造审计 |
| V2-07 | 不存在的/缺失的物品体积可被当作 0 运费或形成无穷大利润密度。**HISTORICAL（已针对 V3 修过，但要回归）** | 缺失/非正/无穷体积、未验证打包/组装状态必须 fail-closed | GitHub PR #28、Issue #25 |
| V2-08 | BPC 产品级过早去重、候选池挤占，可能遗漏不同合同的执行利润。**REQUIRES_RECHECK** | 发现层按产品族保留多个实例、分配轮换与多样性额度；验证层只根据真实证明排序 | Notion 2026-09-27/29 审计 |
| V2-09 | Python 扫描逻辑使用字符串补丁/动态 compile，难以调试和签名验证。**REQUIRES_RECHECK** | 新版本全部为显式模块、依赖注入、无运行时文本改写生产源代码 | 旧审计 runner.py / runner_buy_only.py |
| V2-10 | 依赖 V2 等级标签的旁路发信可能绕开正式 MAIL Gate。**REQUIRES_RECHECK** | 任何渠道只能消费统一已批准 Proof/Decision，所有其他信号研究专用 | 旧审计 Global A/S grade-watch |

## B. V3 运行/提醒/状态/模型
| ID | 故障及证据状态 | 新版禁止重演的约束 | 证据 |
|---|---|---|---|
| V3-01 | 15 分钟触发而扫描常超过 15 分钟；历史 49 轮中 17 失败、31 取消，整体成功少。**HISTORICAL** | 每航道显式状态机、锁与跳过拥塞；每轮 stage 预算和运行时间水位预警，失败不能冒充成功 | Issue #26 |
| V3-02 | C-J 建筑市场/合同因 ESI 403 与建筑 ACL/鉴权出错，恢复后还需持续健康检查。**HISTORICAL** | 将 UNAUTHORIZED、MISSING_SCOPE、ACL_DENIED、UPSTREAM_5XX 独立分类；验证首屏成功才解禁相应航道 | Issue #26；PR #28 |
| V3-03 | 旧 DC shadow 绿色 run，却因访问失败跳过所有实际扫描。**HISTORICAL** | 无有效数据时报告 WAITING_FOR_ACCESS / SKIPPED，不得称扫描成功；旧 shadow 已删除，O4T 生产独立核验 | Issue #26；PR #30 |
| V3-04 | BPC 曾在 Cloudflare 被暂停、旧快照仍显示在新汇总中。**HISTORICAL** | 每行 Proof 带 source_run_id、generated_at、TTL、scan health；过期=不可 MAIL | Issue #26 |
| V3-05 | Workflow 持久化前执行 git reset，却未保存 candidate_pool_state.json 和 v3_contract_fingerprints.json；多轮 SHA 不变，候选历史停留旧日期。**CONFIRMED，PR #34 修复** | 状态必须使用事务性持久库；不能依赖 git reset 前的本地文件并假设提交成功 | PR #34；2026-10-10 至 10-12 多轮 Blob SHA 不变 |
| V3-06 | 游戏邮件凭上一轮 TOP 名单波动、整频道变更重发全部旧机会；10 月 12 日生产再次重发。**CONFIRMED，PR #35 修复** | 机会实例级唯一身份 + 独立 Outbox；TOP 排名不是「新机会」；更新/消失/重现须回放测试 | PR #35；运行 #38259875500 |
| V3-07 | 市场 Gmail 6 小时后按绝对利润/ROI 波动再提醒，恶化与回到榜单也可能触发。**CONFIRMED，PR #34 调整** | 把恶化、真实改善、订单换新拆开；冷却时间不等于新的执行标的 | Issue #33，PR #34 |
| V3-08 | 市场去重只按 channel + type_id，不能识别同类商品的新卖单、真实新订单簿。**UNRESOLVED** | MarketFamily/type_id 与 MarketInstance/verified order_id 有不同 ID；缺 order_id 时不虚构确定的新单 | Issue #33 |
| V3-09 | v3_source_market_scanner.py、v3_structure_contract_scanner.py 中 market_change_pct=0.0；政策的 MARKET_CHANGED 防护无法正确判定。**UNRESOLVED** | 真实新旧可比执行报价计算变化率；缺基线=UNKNOWN，不允许把 UNKNOWN 表示 0 | Issue #33；源文件 |
| V3-10 | EVE 游戏邮件发送遇 CCP/ESI 520 限流；多频道逐封发送与重试放大问题，LadyBaBa 漏收。**HISTORICAL，PR #30 缓解** | 统一收件人合并摘要、负载限制、退避/停止限流重试、保留未送达状态，外部投递不许假定 exactly once | Notion 2026-10-10；PR #30 |
| V3-11 | 外部 ESI mail 发送后进程失败或状态文件未写入，可能再次发同一消息。**STRUCTURAL RISK** | Outbox transactional claim/ack，外部超时设 DELIVERY_UNCERTAIN、人工复核；不可将「未确认」等于「一定未送达」 | PR #35 所修仍非端到端事务 |
| V3-12 | 正式交易审计 trade_realized_audit.py 读取老 mail_last / mail_push_history，未纳入新 mail_seen_v3 完整累计身份；新 V3 部分市场/现金合同未完整归因。**UNRESOLVED** | 机会 ID 是通知和采购/转移/销售共用外键；成交流程提供可验证联结和未知库存隔离 | trade_realized_audit.py；Issue #27 |
| V3-13 | Approved BPC 路线图要求远端 V2 SAFE + 100M/15%/50M 与 Jita 四关；生产适配器曾只用 Jita 四关。**UNRESOLVED POLICY CONFLICT** | 独立政策版本 + 显式用户批准；默认冻结已批准的更严格条件，新版上线前必须对账决议 | Issue #27 |
| V3-14 | GitHub main 被用作高频数据库：近期抽样 100 次 commit 中 92 次为 data 更新，历史膨胀和并发提交压力显著。**CONFIRMED** | 主分支只有代码/治理与 release；业务事实入 DB / 对象存储，只有重要报表按需归档 | GitHub commits/main，2026-10-12 |
| V3-15 | README 仍写 V2+V3、旧 Cron、旧收件角色；Notion 截至 10 月 10 日未包含 10 月 12 日修复；Airtable Runs 状态滞后。**CONFIRMED** | 机器生成生产拓扑和版本清单；工作台由最终运行状态同步，不把旧手册段落当作现状 | README、Notion、Airtable Projects/Runs |
| V3-16 | Airtable Opportunities 表只有 3 条可转债，EVE 机会为 0；虽然 GitHub 扫描有大量输出但无法在 Workbench 查机会生命史。**CONFIRMED** | 每个 MAIL-worthy instance 入中心机会库，Airtable 持有索引/汇总；首次、再次、通知、采买与结算可对账 | Airtable Opportunities 2026-10-12 |
| V3-17 | 多次 CI 绿色只证明函数/离线流程合格，不证明连续生产不重复或实际买盘有效。**CONFIRMED PROCESS GAP** | 历史 replay + shadow + 首轮真实生产 + N 轮连续回归；区分 scan success、delivery success 和 profit attribution | PR #34/#35、Run #38259875500 |
| V3-18 | 一些工作流（例如 booster-monitor）在 Push 时默认仍会执行可发送真实邮件的脚本，正式 Roadmap 禁止 Push 发信。**CONFIRMED ARCHITECTURE RISK** | 所有 PR/push 必须 dry-run，真实邮件仅专用运行权限 + 已批准部署触发 | booster-monitor.yml / ROADMAP_GOVERNANCE.md |
| V3-19 | 多次通过「名义修复」解决一个重复来源，但旧机制在不同角色、不同渠道、TOP 变化、失败恢复场景继续出问题。**CONFIRMED GOVERNANCE GAP** | 先写不变式和系统测试矩阵再改代码；修改通知/状态必须覆盖历史事故 fixture | PR #34/#35 和用户实际收到的旧机会 |


## B2. 2026-10-13 补充审计：为何 V3 曾经精准、后来越跑越差

下列是经过源码、持久状态和历史 GitHub Actions 日志核实的机制；问题发生时间与现状分开。少推送不一定代表没有真正新机会。

| 编号 | 机制与状态 | 业务影响及回归要求 |
|---|---|---|
| V3-20 | **先 TOP 截断，后排除旧机会（CONFIRMED 代码风险）**。send_v3_opportunity_mail.py 中 build_candidates 从合格名单取市场前10/合同最多前10，main 才调用 pending_candidates。 | 若前10长期都是 seen ID，排名11及以后全新机会不被检查。应对所有通过 Gate 的机会先按 instance 判新旧，再从未通知的新机会按分数选 TOP。实际漏报数量尚待历史回放。 |
| V3-21 | **终生 type_id 去重（CONFIRMED）**。市场渠道的 id_col 是 type_id，mail_seen_v3-cj-to-jita_MikeChong.csv 已包含2969、14114、41058。 | 同商品次日出现不同卖单仍是 seen，真正新订单被屏蔽。MarketFamily/type_id 和 MarketInstance/真实 order_id 指纹要分离。合同的 contract_id 终生去重不同，通常合理。 |
| V3-22 | **首轮迁移把当前 TOP 视作历史已通知（CONFIRMED 代码风险）**。seen_path 不存在但旧 mail_last 存在时，pending_candidates 将 picked 全部加入 baseline 而不查询是否实际送达；Gmail首轮也以 current_id 初始化。 | 当轮刚出现的新机会可能被永久误记为已发送。应明确 VERIFIED_SENT、MIGRATED_SUPPRESSED、UNKNOWN 三种语义，禁止假装已发信。 |
| V3-23 | **扫描吞吐下降（CONFIRMED）**。GitHub Actions 10月7日抽样55轮成功26、取消27、失败2；10月8日96轮成功17、取消76、失败3；10月9日96轮成功2、取消82、失败12。10月7日成功示例#37612823001约10分钟；10月8日#37859786667约15分钟；10月9日#37902288039在下一15分钟轮次来时被取消。公开候选快照的 universe 示例从6426增加到约24k，口径可能变动，不能当市场规模直接变化。 | 成功轮次骤减，候选检测、发信与落盘都不可靠。新的排他调度应跳过 busy，记录 stage 耗时、吞吐、最后成功时间并隔离失效源。 |
| V3-24 | **并非所有状态都会无限积累（CONFIRMED）**。candidate_pool.py 只保存最近8轮，不是无限黑名单；它在10月7日至12日停滞是 Git 状态持久化缺失（PR#34已修）。v3_contract_fingerprints.json 每轮全量替换；相反 mail_seen_*、gmail_seen_* 和市场 Gmail 状态并无明确过期规则。 | 为所有状态定义生命周期与用途，区分有限候选轮换、可覆盖快照、持久发送身份和可能过期的报价状态。 |

10月12日已完成 run #38272627567：公开正式候选1个、C-J市场正式候选3个，游戏内通知对两个角色均为无新提醒；这证明扫描仍找到候选但已按旧ID抑制，不证明所有候选均为新的订单。Issue #33 记录10月9日至12日 Gmail 通知39条里12条是相同渠道身份重复（30.8%），因此早期「多」可能部分是重复，不等于全是独立套利机会。

**后续验收：** 同时展示通过 Gate 数、真正新实例数、已发送实例数、实际订单变化数、漏报数与已实现利润。不得用清空 seen、缩短冷却期或降低正式净利润门槛追求邮件数量。

## C. 必须保留的正向成果
- EVE ESI / EVE Ref / Cloudflare Worker 的 SSO、公开与建筑市场和合同读取能力；已确认部分建筑 ACL 在符合条件时可用；鉴权实例保留。
- 两种真实订单簿方向：来源最低卖单成本，目的地真实买单分层兑现；当订单深度不足或价格压力测试失败则不计虚拟流动性。
- FULL_CASH / PARTIAL_CASH_FLOOR / BARTER / LIST-SUPPORTED 的经济区别，后者 WATCH-only；BPC 与 >5B 高价值合同独立风险政策。
- 适度多样化的候选召回与透明拒绝漏斗（raw → prefilter → verified → MAIL）。
- MikeChong + LadyBaBa 采购、LadyGuaGua 集中销售；净利>=50M、非 BPC 利润密度>=2000 ISK/m³；已批准风控不能通过重写悄悄变更。

## D. 每项事故形成可运行的 fixture（验收目标）
- **TOP 2→1→2**：旧合同只通知一次，新合同另行通知。
- **市场新订单**：同 type_id 的真实 order_id 更换才可标记 instance 新发现；价格/ROI 恶化不重发。
- **API 403 / 502 / 520**：分别降级、独立记录、没有假数据污染和邮件风暴。
- **BPC 旧快照**：过期的旧 MAIL 行不得混入新一轮汇总或出现在通知候选。
- **Market Change**：超过 15% 的比较结果按政策处理；基线缺失不能传 0。
- **体积为 0/缺失**：正式 MAIL 结果为 0；已知真实体积能通过正常风控。
- **Outbox 确认与超时**：重复触发不会重复创建事件；不确定送达不会无脑重试。
- **仓储重启/并发**：多 Worker / 多 GitHub Run 同一机会只形成一个 pending 通知。
- **利润归因**：未识别库存不得混入捡漏 FIFO；MikeChong/LadyBaBa 的采购可正确关联 LadyGuaGua 出售；人工采购与告警必须明确关联。
- **CI 全绿仍需 72h shadow**：无未验证订单可自动推荐、无旧消息重推、输入/状态可重放。

## E. 待补齐的原始证据档案
旧的全量源代码、Git tag/commit SHA、issues、PR diff、最近可定位 scan 快照/订单 ID、邮件发送日志、未发成功的外部 mail_id、Notion 9/27 审计、批准过的 BPC 策略版本及三角色审计报告；不足证据的条目不能写为「已关闭」。

**状态：经验档案 Draft，不是全面代码取证已完成；重建过程逐条添加 regression fixture、复现日志和真实关闭证据。**