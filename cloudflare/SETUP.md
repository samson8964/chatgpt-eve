# Cloudflare：EVE 单角色授权、邮件和窗口服务

源码为 [worker.js](worker.js)，工作流部署名为 `eve-contract-opener`，扫描脚本使用的服务地址为 `https://eve-contract-opener.99617224.workers.dev`。它提供邮件中转、合同/市场窗口和技能读取，**不执行合同扫描或估值**。

## 单角色共享架构

KV 只有一组 `refresh_token`、`character_id`、`character_name`，所有调用共用该角色，不按访问者或收件人隔离。使用 LadyGuaGua 发信时，应保留其授权；重新授权为 MikeChong 等角色会替换共享身份，影响邮件、技能和窗口操作。

`/c/合同编号` 和 `/m/物品编号` 操作的是 **Worker 当前授权角色的游戏客户端**，不是网页访问者或邮件收件人的客户端。角色需在线，接口调用仍可能失败。游戏邮件中的 `contract:0//合同编号` 是另一种客户端内链接，不能与 Worker 网页链接混为一谈。

## 部署所需配置

为 Worker 绑定 KV，绑定变量名必须为 `AUTH_STORE`，KV 命名空间可自行命名。

| 保存位置 | 名称 | 用途 |
|---|---|---|
| Worker 普通变量 | `EVE_CLIENT_ID` | EVE 开发者应用编号 |
| Worker 普通变量 | `EVE_REDIRECT_URI` | 官方登录回调；当前为 `https://eve-contract-opener.99617224.workers.dev/callback` |
| Worker Secret | `EVE_CLIENT_SECRET` | EVE 应用密钥 |
| Worker Secret | `MAIL_API_KEY` | 邮件和技能接口访问密钥 |
| GitHub Actions Secret | `EVE_MAIL_API_KEY` | 扫描调用 Worker；值应与 Worker 的 `MAIL_API_KEY` 一致 |
| GitHub Actions Secret | `CLOUDFLARE_API_TOKEN` | 部署 Worker 使用 |
| GitHub Actions Secret | `CLOUDFLARE_ACCOUNT_ID` | 部署目标账户编号 |

不要把密钥或刷新令牌写进源码、文档、公共结果或日志。部署工作流不会创建 KV、EVE 应用或填写 Worker 运行变量。

EVE 应用需注册相同回调，允许当前源码申请的三个权限：

- `esi-ui.open_window.v1`：打开合同、市场窗口。
- `esi-mail.send_mail.v1`：发送邮件。
- `esi-skills.read_skills.v1`：读取授权角色技能。

运行 [Deploy Cloudflare EVE Worker](../.github/workflows/deploy-cloudflare-worker.yml)。工作流先做 Wrangler 构建预检，再部署；命令使用 `--keep-vars`、`--strict`，名称和兼容日期写在工作流中。更换名称、域名或回调时，还需检查 Python 调用地址：部分通用入口读取 `EVE_MAIL_WORKER_URL`，增效剂 `relay.py` 及部分链接生成代码则使用固定地址。

部署与角色授权是不同步骤。首次配置后访问 `/auth`，在 EVE 官方页面授权指定角色；新增权限后也需重新授权现有角色。正常刷新时 Worker 保存 EVE 返回的新刷新令牌。

## 路由和实际行为

| 路由 | 行为与条件 |
|---|---|
| `/`、`/health` | HTML 状态页，显示保存的授权和角色，不要求 API Key |
| `/auth`、`/callback` | 官方登录及保存授权，校验浏览器中的 OAuth state |
| `/logout` | 清除保存的共享角色授权；当前访问路径就会执行，不是只读检查 |
| `/c/合同编号` | 为共享角色打开合同窗口；刷新失败时进入重新授权流程 |
| `/m/物品编号` | 为共享角色打开市场窗口 |
| `GET /api/skills` | 要求 `Authorization: Bearer <MAIL_API_KEY>`，返回共享角色技能点字段、技能列表和派生统计 |
| `POST /api/send-mail` | 要求同一 API Key，接收 `recipient_id`、`subject`、`body` 和可选 `idempotency_key`，从共享角色发信 |

扫描器目前没有使用技能接口自动设置制造技能或市场税率。`allocated_sp` 等派生字段按 Worker 公式计算，不能据接口存在就宣称利润模型使用了真实角色技能。

邮件成功时返回 `mail_id`、`sender_id` 和 `recipient_id`。相同 `idempotency_key` 成功发送后在 KV 保留 48 小时去重标记；命中时返回 `skipped: true`，不返回原邮件编号。这是有限期限的去重，不是永久合同台账或严格的并发单次投递保证。

## 验证与当前边界

可以只读检查 `/health`，但“已授权”只证明存有授权记录。页面权限来自源码常量，也不证明旧令牌已获得新增权限。发信成功应看具体投递编号，技能可用性应看带正确密钥的技能接口结果。

[Cloudflare worker smoke test](../.github/workflows/worker-smoke-test.yml) 检查健康页和技能接口未带密钥时的拒绝响应，不验证真实技能权限。[EVE mail test](../.github/workflows/mail-test.yml) 会真实向 MikeChong 发测试邮件，不是无副作用的健康检查。

当前仅 `/api/send-mail` 和 `/api/skills` 检查 API Key；`/auth`、`/logout` 和窗口路由没有额外管理鉴权。因此这是共享单角色工具，不是具备用户隔离和完整管理权限控制的多用户服务。`/logout` 只删除本服务保存的授权，代码没有调用 EVE 令牌撤销接口。

增效剂本机程序另用 PKCE 和 Windows 加密文件保存授权，不会自动获得 Worker 的授权或密钥。两种模式的区别见 [增效剂 README](../booster-monitor/README.md)。
