# EVE V4｜Arb Hunter 五站采购扫描｜2026-11-09

## 目标与精确建筑ID

用户提供游戏内 UALX-3 原生 showinfo 链接：
`Arb Hunter > <url=showinfo:35834//1046664001931>UALX-3 - Mothership Bellicose (BC Piggy)</url>`。
该信息确认了精确建筑ID `1046664001931`，无须再人工指定结构ID。

仅扫描以下五个玩家建筑（不将 Jita 4-4 算作此五站的采购来源）：

| lane | 私人建筑 | structure_id | auth_profile |
| --- | --- | --- | --- |
| banestar | 74L2-U - BANESTAR - BALLS DEEP EDITION | 1050474463169 | dc (Arb Hunter) |
| cj | C-J6MT - 1st Taj Mahgoon | 1049588174021 | dc (Arb Hunter) |
| o4t | O4T-Z5 - Dracarys. Prime | 1040804972352 | dc (Arb Hunter) |
| r_arkn | R-ARKN - BIG MOM | 1048663825563 | dc (Arb Hunter) |
| ualx | UALX-3 - Mothership Bellicose (BC Piggy) | 1046664001931 | dc (Arb Hunter) |

前3个ID来自当前 V4 authoritative structure registry；R-ARKN 来自 EveSynapse 公开结构信息（实际访问仍须ESI认证核验）；UALX 来自用户本人EVE showinfo链接。图片的“路线数”不是订单数或成交额。

用户确认 **DC影子市场授权成功**，但这只表示 EVE SSO callback 接受了授权，不代表五站市场实际 ESI 200；程序仍需核实 `dc` 返回的角色确实是 `Arb Hunter`。

## 安全架构与部署状态

GitHub准备分支 `prep/v4-windows-local-migration-20261013`：
- `v4/structure_registry.py` 设定五个精确ID和 `HUNTER_FIVE_LANES`。默认仍使用旧C-J、O4T和条件性BANESTAR配置（四H已退役）。
- `v4/hunter_purchase_probe.py` 通过同一Worker `auth_profile=dc` 核实 Arb Hunter ESI角色身份，直接对五个固定建筑逐站只读抓第一页，`--full` 时抓完整分页，报告真实订单数。
- `--full --activate-on-success` 为**单次显式切换命令**：仅当五个建筑都 `COMPLETE` 且页数完整、角色精确匹配时，原子写入本机私有启用哨兵 `%USERPROFILE%\\EVE-V4-Data\\config\\hunter-five-station.enabled`，令下一轮 **V4 Shadow 研究扫描**统一通过 Arb Hunter `dc` 授权抓五站。
- 这不会修改 Cloudflare Worker 的其它角色凭据、GitHub secret、Windows计划任务、MAIL正式推送、用户现有SQLite历史数据，且不执行购买/下单。
- 新建哨兵的存在本身并不等于下一轮已成功；必须检查下轮 `structure_health` 五站全部 `COMPLETE`、`pages_fetched == pages`。
- 默认旧 BANESTAR `banestar` profile在正式的五站模式启用后停止被使用，但其KV保存的授权不会被删除；取消五站模式可回退原有范围。

## Windows执行（一次性五站验收+安全启用）

用运行 `EVE-V4-Shadow` 计划任务的 Windows 用户登录。不可在任务 Running 时更新代码；也不要把bridge key / EVE SSO令牌贴到聊天。

```powershell
$repo = Join-Path $HOME 'EVE-V4-Code'
$task = Get-ScheduledTask -TaskName 'EVE-V4-Shadow' -ErrorAction Stop
if ($task.State -eq 'Running') { throw '扫描正在运行，禁止在此时修改配置' }
$branch = git -C $repo branch --show-current
if ($branch -ne 'prep/v4-windows-local-migration-20261013') {
    throw "分支不符：$branch；不自动切换或覆盖本地代码"
}
git -C $repo pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'git pull失败，不修改配置' }
Push-Location $repo
try {
    & .\.venv\Scripts\python.exe -m v4.hunter_purchase_probe --expected-name "Arb Hunter" --full --activate-on-success
    if ($LASTEXITCODE -ne 0) { throw '五站权限/分页验收失败，未启用新扫描模式' }
} finally { Pop-Location }
```

成功时返回：
- `authorized_character: Arb Hunter`，且有正整数 `authorized_character_id`
- `banestar/cj/o4t/r_arkn/ualx` 全部 `status: COMPLETE`
- 每站 `pages_fetched == pages_reported`，提供 `orders_count`
- `activation.status: HUNTER_FIVE_STATIONS_ENABLED_FOR_NEXT_V4_RUN`

若任一站 `HTTP_FAILURE`（401/403等）、`FULL_PAGINATION_FAILED`、`INVALID_PAGE_COUNT`，或角色名错为 `Abr Hunter`，整体验收失败，**不会创建新哨兵**。如果此前已经激活过五站模式，不会自动清除上一次已成功的哨兵。

因用户已要求一次性配置，**不用再单独输入 `--ualx-id`**，也不用先运行四站再补UALX。

## 下一轮结果验收

切换成功后，不触发额外并行扫描，保持既有 `EVE-V4-Shadow` 计划任务。在下一次正常扫描结束后检查：
- 五站 `structure_status` 均 `COMPLETE`
- `structure_order_counts` 五站数量和总数
- `coverage_gate`、`source_input_integrity`、SQLite 对账、市场候选的来源站及 Jita 买单价值依据
- 正式邮件推送 `EVE-V4-Opportunity-Push` 仍 Disabled，采购仍需用户游戏内操作。

真实交易购买需要另行授权，市场读取 scope 并不能自动下单。

## 安全回退

如果新模式下一轮发现明显问题，等待 Shadow 不在 Running 后，仅删除新模式的精确哨兵文件，下一次新启动的扫描进程会自动使用以前的 registry 默认配置，旧授权及历史数据不丢失。

```powershell
$task = Get-ScheduledTask -TaskName 'EVE-V4-Shadow'
if ($task.State -eq 'Running') { throw '等待扫描结束再回退' }
Remove-Item (Join-Path $HOME 'EVE-V4-Data/config/hunter-five-station.enabled') -ErrorAction Stop
```

**状态边界**：GitHub源码准备及CI测试不等于Windows本地已git pull、五站已实测或已正式启用。务必以用户机器的五站 `COMPLETE` 和后续 Shadow 真实结果为准。


## 2026-11-09 Windows desktop monitor five-station compatibility

Updated:
- `v4/desktop_station_monitor.py`: recognizes the exact `hunter-five-station.enabled`
  sentinel as the authoritative *local* monitored scope. Displays all five
  lanes, not retired `four_h`, and prevents old two/three-station reports
  from falsely turning the monitor green after five-station activation.
  A current five-lane green status needs complete per-lane pagination
  and the normal shadow coverage gate. Newer failures remain failures.
- `v4/desktop_status.py`: exposes `hunter_enabled`, `scan_scope_name`,
  `active_lanes`, `private_market_orders`, `private_market_pages`.
  Old-run model metrics and SQLite proofs stay hidden until first verified
  full-scope shadow run.
- `v4/desktop_widget.py`: shows C-J/UALX-3/R-ARKN and O4T/BANESTAR on two
  compact lines, with the retired 4-H noted. A separate market count/page
  row uses only a verified *V4 shadow report*, not the independent
  Arb Hunter permission probe. Opportunity section is scope-aware and
  never claims zero qualified opportunities while the push report is
  absent or incomplete.
- `v4/tests/test_desktop_hunter_five_station.py`: regression coverage for
  pre-activation historical green reports, complete five-lane reports,
  missing or incomplete pages, newer failed runs, running task with a
  prior valid run, wrong marker, and old-scope push reports.

After the V4 Shadow task is **not Running**, update the same local
GitHub checkout as the scheduled scanner with `git pull --ff-only`.
The existing `EVE V4 Monitor.lnk` shortcut already invokes
`-m v4.desktop_widget` from the checkout, so **the shortcut need not be
reinstalled**. Close the old monitoring window and relaunch the
existing desktop shortcut to load the new code. The monitor itself
remains read-only except for the user's existing explicit
"立即全面扫描" button; relaunch does not trigger a scan.

The independent five-station permission preflight (79,009 orders/81
pages, 2026-11-09) is not an actual scheduled full V4 Shadow scan.
Do not display that historical probe count as current market volume.

