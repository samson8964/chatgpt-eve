# HY-RWO | Arb Hunter 第六座建筑扫描接入（2026-11-10）

## 用户提供的精确建筑身份

EVE 游戏内角色：**Arb Hunter**，已核实人物 ID **2124830062**（来自已完成的本机邮件配置验收）。
用户直接复制 EVE showinfo：

```
<url=showinfo:35834//1049633275448>HY-RWO - Time Is A Flat Circle (Sensible People)</url>
```

- 地址标签：`HY-RWO`
- 精确建筑 ID：`1049633275448`
- `structure_registry.HY_RWO_LANE = ("hy_rwo","HY-RWO",1049633275448,"dc")`
- 直接复用当前已验证的 Arb Hunter **DC** SSO 档案；**不修改 Cloudflare Worker/密钥**，无需增加 EVE SSO scopes。
- 旧五站：74L2-U、C-J、O4T、R-ARKN、UALX-3 维持原样；4-H 保持退役。公开 NPC 市场和合同分析不变。

## 安全接入分为两阶段

1. **仓库支持（已完成）**：新站在 Hunter Five 模式上作为第六站，只在本地存在**精确匹配**的 `EVE-V4-Data/config/hunter-hy-rwo.enabled` 文件时进入任务的 `STRUCTURES`。没有标记时旧五站扫描完全不变。
2. **本地实时验收（尚未完成）**：使用 Arb Hunter DC 当前授权对这一建筑只读探测首页及全量分页，验证每页结构ID、一致页数、订单ID、地点、类型、价格和方向，之后自动创建第六站启用标记。无需重新扫一次公开全市场。

市场访问授权由 **EVE ESI实际返回** 决定，建筑名称、showinfo 链接和军团成员身份都不证明 `esi-markets.structure_markets.v1` 可读。出现 403/401、刷新失败、分页不完整或订单校验失败应保持原五站模式，不能声称第六站已接入生产。

## 在拥有 EVE-V4-Shadow 的同一 Windows 用户下执行

**确保计划任务不是 Running**，确认当前 Git 分支不是 `main` 也不是其他未检验分支：

```powershell
$repo = Join-Path $HOME 'EVE-V4-Code'
$task = Get-ScheduledTask -TaskName 'EVE-V4-Shadow'
if ($task.State -eq 'Running') { throw '扫描尚在运行，勿切换采集范围' }
$branch = git -C $repo branch --show-current
if ($branch -ne 'prep/v4-windows-local-migration-20261013') {
    throw "请先核查代码分支，目前是 $branch；勿强行切换"
}
git -C $repo pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull失败；没有启用新站' }
Push-Location $repo
try {
    # 阶段1：只读第一页，检查Arb Hunter和HY-RWO真实市场ACL
    & .\.venv\Scripts\python.exe -m v4.hy_rwo_enrollment
    if ($LASTEXITCODE -ne 0) { throw 'HY-RWO 首页检查失败，不启用新站' }

    # 阶段2：全分页 + 行有效性校验，通过后原子启用第六站
    & .\.venv\Scripts\python.exe -m v4.hy_rwo_enrollment --full --activate-on-success
    if ($LASTEXITCODE -ne 0) { throw 'HY-RWO 全量校验未通过，旧五站仍正常' }

    # 核对第六站已加入当前 Python 运行时注册表
    & .\.venv\Scripts\python.exe -c "from v4.structure_registry import STRUCTURES; print(STRUCTURES)"
} finally { Pop-Location }
```

预期：`FULL_PAGES_VERIFIED`，`activation.status=HY_RWO_ENABLED_FOR_NEXT_SCHEDULED_V4_SCAN`，`STRUCTURES.hy_rwo = (1049633275448,"dc")`，其他五站保留。

若第一步显示 `DC_CHARACTER_MISMATCH`，先查看实际 Worker 页面 `https://eve-contract-opener.99617224.workers.dev/` 的 DC 已授权角色；不得盲目在聊天里贴令牌，也不得清除/覆盖现有可用的其他市场授权。若 Arb Hunter 未授权，可在本人浏览器使用 `/auth-dc` 完成官方 EVE SSO，随后重试。

## 验收条件

启用成功后下一轮 **既有** `EVE-V4-Shadow` 扫描（无需重新安装计划任务）必须：

- `structure_health` 包含 `banestar, cj, o4t, r_arkn, ualx, hy_rwo` 六条记录，各自 `status=COMPLETE` 且 `pages_fetched=pages`。
- `coverage_gate=INPUT_LANES_REPORTED_COMPLETE_NOT_LIVE_VERIFIED`，不能以旧五站成功数据冒充新六站成功。
- `deep_shadow.json` 中 `contract_station_summary.stations.hy_rwo.location_id=1049633275448`，仅涵盖公开 ESI 合同快照；私人或访问受限合同不在此统计范围。
- Windows 监控显示 `HUNTER_SIX` / `HY-RWO ✓`；显示新六站市场/合同的分类统计，没有对当前运行范围使用过期的五站证据。
- 游戏研究邮件继续 `MikeChong` + `Arb Hunter`，Gmail不变；不以本次注册表扩展为由开启 `EVE-V4-Opportunity-Push` 或任何正式交易信号。

若真实扫描HY-RWO失效，扫描会保留故障诊断且 `coverage_gate` 降级（fail closed），不把部分订单视为完整市场。短期回退只需在**非运行期间**将本地配置 `hunter-hy-rwo.enabled` 改名为 `hunter-hy-rwo.disabled`，下次恢复旧五站；历史扫描证明不删除。

**代码提交不等于Windows已激活。** 只有用户本机启用标记及后续完整扫描证明，才能把 EVE V4 状态写成“六座建筑真实扫描成功”。
