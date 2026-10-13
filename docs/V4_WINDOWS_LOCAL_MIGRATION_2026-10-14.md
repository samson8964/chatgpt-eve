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

## 今日无需用户操作；明日仅需配合

1. 电脑开机并确保网络/代理可正常访问 EVE Ref、Cloudflare 的现有授权桥；不要发送 API 密钥到聊天。
2. 在电脑终端运行一次 `py -3.11 -m v4.local_preflight` 并反馈**脱敏**的检测结论（磁盘容量、Python/SQLite/包状态即可）。
3. 明天确定保存数据库的盘符及是否允许计划任务在登录后自动运行；本计划不代替你的实际授权和机器端部署。

## 严格不做

- 不恢复 V3、不开正式邮件；不将 Draft PR #53 当作主线。
- 不要求向公有仓库泄露 ESI 授权；不在 GitHub Actions/Cloudflare 恢复付费 SQL 操作。
- 不在未验证真实订单成交条件时宣称盈利或已完成正式 V4 上线。
