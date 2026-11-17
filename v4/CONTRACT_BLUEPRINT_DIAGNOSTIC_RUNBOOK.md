# V4 合同与蓝图漏斗诊断（2026-11-10）

## 问题与已核实证据

用户上传的 Windows Shadow 总任务日志 2026-10-14 至 2026-11-10：
- 538 个 RESULT；487 SHADOW_RECORDED，46 DEGRADED_PARTIAL_COVERAGE，5 SKIPPED_UPSTREAM_STALE。其他早期 FULL_SCAN 失败和未完成轮次不在 RESULT 计数中。
- 2026-11-10 17:23 北京时间启动的已完成轮次：六座 Upwell 建筑均 COMPLETE，研究 Gmail 合同1、游戏邮件 MikeChong 和 Arb Hunter 各API成功；上传日志最后 18:23 开始新轮后截断。
- 已连接 Gmail 额外确认 11-10 18:23 研究邮件发出：市场10、合同1、蓝图制造0。
- 11-09 15:55 至 11-10 18:23 的28封研究邮件仅6个不同合同ID，蓝图仅同一合同 237989967（BPC 86021）在两封邮件出现。
- 整个 10-14 至11-10 期间共检索468封统一研究邮件，429封标题包含蓝图数字，132封报告蓝图>=1；这些132封中268个显示位置对应46个不同蓝图合同ID、18个蓝图类型。邮件展示是候选的重复快照，不是268个独立捡漏。

## 漏斗实际代码路径

1. `full_scan.py` 使用 EVE Ref 的全公开市场/公开合同快照，不是实盘ESI私人合同或全部私人建筑合同。
2. `deep_scan.py` 仅对批准地点的 `item_exchange` 及无额外 requested items 的合同深入估值；Jita4-4 BUY depth 为估值出口。
3. `contract_partial.py` 允许按可清算普通商品子集估值，未计价商品按0处理；蓝图 BPC/BPO 在此**不能直接按照商品现价折现**。所选子集为按 ISK/m³ 降序的前缀和单项，不是所有可能组合。
4. `contract_content_policy.py` 要求净利>=50m ISK、ROI>10%（部分清算），能量炮晶体价值占比<50%；`ship_alert_exclusions.py` 排除资本舰、货舰及匹配蓝图所在的整份合同。
5. `blueprint_recipes.py` 需要事先安装配方缓存；`blueprint_manufacturing.py` BPO最多10次、BPC不超过授权次数与10次上限，全份合同价格计入单张蓝图选项，材料按吉他 SELL 深度、成品按吉他 BUY 深度，另预留材料费20%与销售税，预计净利>=50m且ROI>10%。材料/成品深度、元数据、路线不完整时可能**不生成任何制造证明**，不是生成一条失败理由。
6. `unified_review.py` 将合格类别按首次发现时间排序，每类最多显示10条；现有邮件每小时重复可见同一合同，并不表示新合同/新蓝图产生。
7. `EVE-V4-Opportunity-Push` 原本 Disabled；当前为 research-only 邮件，不是可执行的实时订单信号。

## 新增只读漏斗检查

```powershell
$repo = Join-Path $HOME 'EVE-V4-Code'
git -C $repo branch --show-current
# 如果不是 prep/v4-windows-local-migration-20261013，先核对分支，不要强行切换。
git -C $repo pull --ff-only
if ($LASTEXITCODE -ne 0) { throw '代码同步失败' }
Push-Location $repo
try {
    & .\.venv\Scripts\python.exe -m v4.contract_blueprint_diagnostics --last 3
} finally { Pop-Location }
```

该命令从最新3个已完成的本机运行文件读取 `full_market_report.json`、`deep_shadow.json`、`all_proofs.jsonl`，输出纯汇总：
- 原始公开合同、授权地点无请求物品的现金合同、排除的 barter 合同等总量；
- 合同 Proof 失败理由、未找到 Jita 买单的货物类型数量、合同中按零计价的蓝图类型数量；
- 扫描时制造配方 `INSTALLED/NOT_INSTALLED/INVALID` 及配方条数；
- 合同中 BPC/BPO/未知实例数量、制造证明条数和符合净利/ROI数、建模错误数；
- 模型候选为快照研究，不表示邮件可达或游戏内仍存在。

它不使用 EVE 登录密钥、不请求网络、不写入 SQLite、不改变任何扫描任务、不发送邮件、不改变正式推送的 Disabled 状态。
若 `blueprint_manufacturing_recipe_status=NOT_INSTALLED`，先核查本地参考文件，不在不知状态时自动安装；安装配方涉及单次网络下载及缓存生成，需要另行执行。
若配方已安装但 BPC/BPO 众多而制造证明很少，下一阶段应增加精确按环节的**弃选原因计数**，但未经用户批准不放宽蓝图制造经济模型或改正式推送方向。

最后必须区分：
- 缺少深度分析报告文件时，仅靠 `shadow-task.log` 的总证明条数不能判定合同或蓝图筛选漏斗的数量；
- 不能把“蓝图制造0”解释为本轮没有任何 BPC/BPO 合同；
- 不能把重复的邮件当成新增的机会；
- 不能把生产/发信成功当成实时可交易确认。
