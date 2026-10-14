# EVE V4 Windows 本地迁移：2026-10-14 实施前清单（准备稿）

> 状态：PREPARED_NOT_DEPLOYED。2026-10-13 仅审阅/提交计划与只读预检脚本。**不安装、不迁移数据库、不建立定时任务、不恢复 V3、不发送邮件。** 用户批准明天（北京时间 2026-10-14）处理迁移。与现有 Draft PR #53 独立，不能把准备工作当作生产部署。

## 目标与边界

- 本地 Windows 机器承接 EVE V4 的采集、计算、SQLite、运行调度和历史研究数据；GitHub 继续做代码版本及 CI；现有 Cloudflare ESI 授权/桥接暂时保留，不主动迁移或暴露授权。
- **全量市场必须每次重新扫描**；CSV/SQLite 历史不能作为跳过已见商品或订单的采集过滤条件。SQLite 历史仅用于通过所有验证后的订单/合同实例去重，以及保留每次审计。
- **邮件全程 OFF**，直到直接 ESI 订单和合同验证、共享买单容量、真实税费/运费/ACL、7 天回放、连续至少 72 小时影子、每 2 小时合并发送及单机运行恢复全部验收。V3 保持停用。

## 已实际核查的 GitHub 事实（以 2026-10-13 main da2daf69 为基准）

| 组件 | 当前代码/状态 | 本地迁移影响 |
|---|---|---|
| `v4/full_scan.py` | EVE Ref 市场订单/公开合同索引，每轮新鲜下载、全面普查；默认 `--data-dir /tmp/v4-market` | Windows 必须显式传入本地数据目录，不能直接沿用 Linux 默认 |
| `v4/deep_scan.py` | 读取市场 `market_orders.csv.bz2`、合同 `public_contracts.tar.bz2`，访问结构市场需 `EVE_MARKET_API_KEY` | Windows 使用与 full_scan 完全一致的绝对路径；Cloudflare ESI bridge 暂不变 |
| `v4/catalog.py` | EVE Ref 类型/蓝图静态字典，默认 `.cache/v4/reference/catalog.json.gz` | 首次下载网络、缓存持久位置/周度刷新需确认 |
| `v4/state.py` | 已有单写者本地 `sqlite3` Ledger，WAL / busy_timeout=30000；表 scan_runs、proof_versions、outbox | **仅是原型**：proof 插入用 INSERT OR REPLACE，返回输入行数并不能证明独立唯一行数；缺事务安全发送认领和 live MAIL 闸门，不得直接作为生产发信账本 |
| `v4/ingest.py` | 专门向 Cloudflare V4 Durable Object 写审核记录 | 本地运行应新增独立 adapter 而非把云端写库路径硬套 SQLite |
| `v4/engine.py` | 订单级盈利计算、深度与压力测试；快照派生 MAIL 会隔离成 WATCH | 暂不修改算法或阈值；订单在发信前仍需直接 ESI 验证 |
| `v4/audit_artifact.py` | Draft PR #53 中新增的离线审核唯一 ID、原因计数、状态、SHA256 | 明天合并前另行核实 PR CI，或以同等严格标准在本地复用 |
| `.github/workflows/v4-market-heartbeat.yml` | 每两小时 cron `23 */2 * * *`；Cloudflare SQL 因免费配额设为 `paused_free_tier`；影子记录存短期 Artifact | 本地调度单独启用并验证连续性；避免 GitHub 影子与本地重复抢占 API；切换前不自动关闭云端 |
| `requirements.txt` | pandas==2.3.3、numpy==2.5.3、requests==2.34.2 | 本地使用 Python 3.11 独立 venv，包安装和版本兼容性必须先实际测试，不能假定已通过 |
| V3 | V3 完全停止；CSV/JSON 去重状态保存于 `results/state/` | 只读保存、导出必要已发历史作通知基线；绝不恢复旧邮件任务 |

## 数据存储分层

1. SQLite **主要状态数据库**（推荐本地单进程写者，WAL）：`scan_runs`、`source_coverage`、`proof_versions`、`orders_last_seen`、`candidate_instances`、`delivery_outbox`、`delivery_attempts`；每轮 `run_id`、唯一复合键及全量行数/状态桶计数。新的 schema 迁移需版本号、幂等和可回滚验证，不能直接把现有 `state.py` 称为生产就绪。
2. 压缩市场源快照：先保留原始 `.csv.bz2` 和 `.tar.bz2` 的内容校验、索引源时间及运行 ID；之后可使用 Parquet 冷存储（选型待测）。**保存原始数据与留存策略要靠磁盘实测**，不要凭 160 万订单数猜大小。
3. 研究审核结果：JSONL+SHA256 原样留档，同时写 SQLite 的 proof/候选索引；读取时比较 `len(proof_jsonl)`、文件内唯一 ID 数、SQLite `COUNT(DISTINCT instance)`、各状态/原因计数，发现差异立即判本轮不可用。
4. 本地数据库原生在线备份使用 SQLite `connection.backup()`，不可直接复制仍在 WAL 写入中的 `.db` 当作可靠备份；每日备份、每周异盘副本、至少执行一次恢复演练。
5. 所有授权只从进程环境或本地秘密存储读取。严禁写入 `.env` 到 Git，严禁将 Token、Cookies、ESI、机器路径包含用户名的预检输出提交为公共 GitHub Artifact。

## 本地目标目录（仅设计，实际磁盘待明日确定）

```
<EVE_V4_ROOT>/
  code/         # git checkout, not the real database
  data/incoming/ # 下载中/最新源快照
  data/history/  # 按 UTC run_id/年月日分层归档
  data/sqlite/v4.sqlite3
  data/audit/    # proofs、manifest、hash
  logs/          # 轮次、错误、耗时、失败原因
  backup/        # 在线数据库备份；另需异盘副本
```

数据库、源快照与秘密文件均置于 Git 工作树之外；不使用 `results/state` 的旧 V3 CSV 当作实时全局写入中心。

## 明日执行顺序（每一步给出可核验证据）

- **P0 环境只读预检**：从仓库根目录执行 `py -3.11 -m v4.local_preflight`（若 py launcher 选择失败改用当前可用 Python）。检查 Windows、Python、内置 SQLite、git、可用存储空间、pandas/numpy/requests 是否可导入；脚本不写盘、不联网、不读取/打印任何令牌。根据真实输出选择目标盘与数据目录，磁盘空间门槛应在量测实际快照压缩比后确定。
- **P0 单独工作树与 venv**：隔离 V3/V4、安装依赖并锁定验证版本，不改 Cloudflare/GitHub 主线。
- **P0 本地扫描**：显式传入 `--data-dir` / `--market` / `--contracts` / `--output` Windows 路径；每次生成独立 `run_id`、源 SHA256、扫描覆盖报告、原因直方图，邮件 OFF。
- **P0 SQLite 初始化/回填**：先仅影子导入，专用事务、唯一键、批量写入/复读验证；同一 run_id 同一 proof 身份内容冲突应拒绝，重复提交相同内容幂等；不可使原型 INSERT OR REPLACE 隐藏差异。
- **P0 完整性对照**：同一输入数据比对 GitHub shadow 和本地输出，抽查 source/结构可访问、source freshness、缺失项、proof 数、重复订单 ID、买卖盘口深度、内存占用、运行时长。
- **P1 计划任务与守护**：Windows Task Scheduler 2h 一轮；无黑框交互、非重叠单实例、重启自动恢复、错过轮次重跑、执行超时/网络失败记录；仅运行 shadow，失败不覆写上轮成功。
- **P1 发送前最终闸门**：ESI live、权限/税运、数量匹配、共享买盘、同机会身份去重、发送后回执以及不确定状态；7 日历史回放与至少 72 小时影子。仅用户审核正式放行后才启用 2h digest。
- **切换/回退**：本地扫描和备份连续达标后，保留云端代码但停用冗余扫描；若本地失败，恢复只读云端 shadow 而非恢复 V3 邮件。单独审计对比最终邮件放行。
- **验收报告**：每轮给出命令/commit/run_id/源快照时间、耗时、row counts（真实 SQL count）、状态直方图、failed lane、是否发送邮件、是否需要用户操作。未现场测得的项目填 `NOT_VERIFIED`。

## 已落实的迁移代码与本机第一次操作（2026-10-14）

准备分支 `prep/v4-windows-local-migration-20261013` 新增：
- `v4/local_preflight.py`：只读检查环境，不联网、不写文件、不读取令牌。
- `v4/local_store.py`：独立单机 SQLite 影子账本，事务插入全部 proof，按 (run_id, instance) 唯一，重复 run 只接受相同源文件，原始 proof 计数、每个状态/拒绝原因、SQLite SQL COUNT 对账；只允许 WATCH/RESEARCH，**没有邮件发送代码**。
- `v4/local_run.py`：明确 `--execute-shadow` 才采集，每次都新拉 EVE Ref 快照并生成独立运行文件夹，数据库于 Git 工作树外，进程锁阻止重复扫描；若建筑授权不可读则标记 PARTIAL_UNVERIFIED，禁止误报完整覆盖。
- `v4/local_backup.py`：SQLite backup() 原生在线备份并检查 PRAGMA integrity_check；另需异盘备份。
- `v4/tests/test_local_store.py`、`test_local_runner.py`：验证正确入库、失败回滚、幂等、非法 MAIL 拒绝与重叠执行阻断。

**Windows PowerShell 初次执行（建议管理员无需提权）**，独立于现有商采工作区，使用浅克隆+稀疏检出减小仓库体积：

```powershell
$repo = Join-Path $HOME 'EVE-V4-Code'
if (Test-Path $repo) { throw "路径已存在，为避免覆盖，请人工确认：$repo" }
git clone --depth 1 --filter=blob:none --sparse --single-branch --branch prep/v4-windows-local-migration-20261013 https://github.com/samson8964/chatgpt-eve.git "$repo"
Set-Location $repo
git sparse-checkout set v4 docs
py -3.11 -m v4.local_preflight
```

预检输出的 `python_311_or_newer`、`windows`、`git_found` 和磁盘剩余量应正常。`missing_dependencies` 此时可为非空（venv 未安装），这不是安装失败。确认磁盘充足后：

```powershell
py -3.11 -m venv .venv
$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
& $python -m unittest discover -s v4/tests -v
& $python -m v4.local_preflight
```

**第一次完整影子采集和 SQLite 入库**（建议先确保目录所在盘空间足够；默认 Windows 用户目录 `EVE-V4-Data`）：

```powershell
& $python -m v4.local_run --execute-shadow --data-root "$HOME\EVE-V4-Data"
```

首次扫描需要读取网络数据与现有授权桥。没有 `EVE_MARKET_API_KEY` 时建筑来源将会 FAILED、被标为 PARTIAL_UNVERIFIED，但**仍可先验证公开市场影子采集**。不要将密钥发送到聊天/公共仓库。扫描完成输出每轮目录、SQLite COUNT、coverage_gate；若失败读取对应 run 目录下 `full_scan.log` 或 `deep_scan.log`。**不要立即安装 Windows 计划任务**，须先实测首次完整影子扫描。

首次影子成功后的在线备份：

```powershell
& $python -m v4.local_backup --data-root "$HOME\EVE-V4-Data"
```

没有本地远程终端/屏幕授权时，聊天端不能直接安装到用户 Windows：以上操作必须在主机 PowerShell 执行并回传无敏感信息的预检与扫描状态。PR 不合并主线、不部署 V3/V4 邮件；正式邮件放行另需用户批准。


## 今日无需用户操作；明日仅需配合

1. 电脑开机并确保网络/代理可正常访问 EVE Ref、Cloudflare 的现有授权桥；不要发送 API 密钥到聊天。
2. 在电脑终端运行一次 `py -3.11 -m v4.local_preflight` 并反馈**脱敏**的检测结论（磁盘容量、Python/SQLite/包状态即可）。
3. 明天确定保存数据库的盘符及是否允许计划任务在登录后自动运行；本计划不代替你的实际授权和机器端部署。

## 严格不做

- 不恢复 V3、不开正式邮件；不将 Draft PR #53 当作主线。
- 不要求向公有仓库泄露 ESI 授权；不在 GitHub Actions/Cloudflare 恢复付费 SQL 操作。
- 不在未验证真实订单成交条件时宣称盈利或已完成正式 V4 上线。

## 2026-10-14 本机第一次反馈：Python 3.11 NumPy 依赖阻塞的实际修正

主机预检 Python 3.11.9、SQLite 3.45.1、Git+Codex 就绪、C盘剩余374.11 GiB，但 `numpy`/`pandas`/`requests` 全部缺失，`unittest` 反馈三处导入错误。根因之一已核实为旧版 `requirements.txt` 硬编码 `numpy==2.5.3`，而 PyPI 官方元数据该版要求 Python >=3.12；3.11安装因此失败。修复后依赖规格：Python<3.12 时 numpy==2.4.3，Python>=3.12 时 numpy==2.5.3；pandas==2.3.3、requests==2.34.2。CI进一步在3.11与3.12分别执行 `pip install -r requirements.txt` 防止再出现同类差错。

**已经 clone 的本机 PowerShell 修复命令（仅修改独立 .venv）：**

```powershell
$repo = Join-Path $HOME 'EVE-V4-Code'
Set-Location $repo
git pull --ff-only
$python = Join-Path $repo '.venv\Scripts\python.exe'
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "安装失败，请保留 pip 错误输出（脱敏后反馈）" }
& $python -m v4.local_preflight
& $python -m unittest discover -s v4/tests -v
```

必须以 `ready_to_attempt_shadow: true` 且测试 OK 为准，不因原来测试抛的错误而直接开始全量市场采集。若 pip 依旧失败，请先根据完整错误判断是代理、证书、镜像源还是解释器路径，**不要**全局关闭 TLS 校验或安装无来源包；不必升级 Python。
