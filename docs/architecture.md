# Architecture

## 目标

本仓库把 ByteDance DeerFlow 包装成一个 Hugging Face Docker Space。目标不是复制上游源码到仓库，而是在 Docker build 阶段拉取上游 DeerFlow，并在 HF Space 中以单容器、多进程、单公网端口方式运行。

`local/` 只作为本机参考目录，不是部署源，也不应进入云端构建上下文。

## 运行时进程模型

```text
container
├─ supervisord
│  ├─ gateway
│  │  └─ uvicorn app.gateway.app:app --host 127.0.0.1 --port 8001
│  ├─ frontend
│  │  └─ pnpm start --hostname 127.0.0.1 --port 3000
│  ├─ ops
│  │  └─ python hfs/services/ops_service.py on 127.0.0.1:8081
│  ├─ admin
│  │  └─ python hfs/services/admin_service.py on 127.0.0.1:8082
│  └─ nginx
│     └─ public listener on 0.0.0.0:7860
└─ /data/deer-flow
   ├─ config.yaml
   ├─ extensions_config.json
   ├─ data/deerflow.db
   ├─ users/<user-id>/...
   ├─ logs/
   └─ .jwt_secret and other generated secrets, when not provided by HF Secrets
```

`hfs/supervisor/supervisord.conf` 是进程源。Gateway、frontend、ops、admin、nginx 都由 supervisor 启动并自动重启。

## HFS runtime glue layout

本仓库是 Pattern A HFS port repository：仓库根目录直接是 Space root，复杂 runtime glue 收在 `hfs/` 下，不再套 `cloud/hfs/`。

```text
hfs/
├─ bin/           entrypoint and Docker healthcheck
├─ config/        managed DeerFlow and extensions config
├─ nginx/         public route proxy
├─ supervisor/    process orchestration
└─ services/      ops/admin Python stdlib services
```

## 构建策略

`Dockerfile` 的主要步骤：

1. 基于 `python:3.12-slim-bookworm`。
2. 安装 `bash`、`build-essential`、`curl`、`git`、`jq`、`nginx`、`supervisor`、`tini`、Node.js 22、`pnpm@10.26.2`。
3. 从 `DEERFLOW_REPO` shallow-fetch 上游 DeerFlow，默认 `https://github.com/bytedance/deer-flow.git`。
4. 检出精确 `DEERFLOW_REF`；当前默认 pin 为 `964162747f4839a954e247bef82f5f69dde8219d`，并记录 upstream SHA/ref/version。
5. 在 `backend` 执行 `uv sync`。
6. 在 `frontend` 执行 `pnpm install --frozen-lockfile`。
7. 执行 `pnpm exec next build --webpack` 生成生产前端。
8. 复制 `hfs/`、`docs/`、`examples/`、`scripts/` 和 README 到镜像。

Next.js 16 默认会在 build/dev 中使用 Turbopack。实际 HF `cpu-basic` 环境中，Turbopack production build 卡在优化阶段；dev server 又会让 `/setup` 卡在 `Loading...`。因此当前显式使用 `next build --webpack`，runtime 使用 `next start`，避免 HMR 依赖。

## Nginx 路由

| Public path | Internal target | 说明 |
|---|---|---|
| `/` | `frontend:3000` | Next.js UI。 |
| `/setup` | `frontend:3000` | 管理员初始化页。 |
| `/workspace/*` | `frontend:3000` | 登录后工作区。 |
| `/_next/*` | `frontend:3000` | Next.js 静态资源。 |
| `/api/*` | `gateway:8001` | DeerFlow Gateway API。 |
| `/api/langgraph/*` | `gateway:8001` | Nginx rewrite 到 Gateway `/api/*`。 |
| `/docs` | `gateway:8001` | Swagger UI。 |
| `/redoc` | `gateway:8001` | ReDoc。 |
| `/openapi.json` | `gateway:8001` | OpenAPI schema。 |
| `/health` | `gateway:8001` | Gateway health。 |
| `/api/sandboxes` | Nginx fixed 404 | HFS demo 不启用 sandbox provisioner。 |
| `/_ops/*` | `ops:8081` | 诊断面。 |
| `/_admin/*` | `admin:8082` | 受限管理面。 |

`hfs/nginx/nginx.conf` 保留 HF 代理传入的 `X-Forwarded-Proto` 和 `X-Forwarded-Host`。这是 auth/CSRF 正常工作的关键，否则 Gateway 可能把公网 HTTPS 请求误判成容器内 HTTP，引发 `Cross-site auth request denied.`。Nginx access log 使用 `$uri` 而不是完整 request URI，主动丢弃 query string，避免 OAuth code 或 token 进入容器日志。

## 配置同步

`hfs/bin/entrypoint.sh` 会解析运行目录并准备 `/data/deer-flow`。关键变量：

```bash
DEER_FLOW_HOME=/data/deer-flow
DEER_FLOW_DB_DIR=/data/deer-flow/data
DEER_FLOW_CONFIG_PATH=/data/deer-flow/config.yaml
DEER_FLOW_EXTENSIONS_CONFIG_PATH=/data/deer-flow/extensions_config.json
DEER_FLOW_MANAGED_CONFIG=true
```

当 `DEER_FLOW_MANAGED_CONFIG=true` 时，entrypoint 每次启动都会把 `hfs/config/config.hfs.yaml` 覆盖到 `DEER_FLOW_CONFIG_PATH`。这是为了让 HFS 仓库中的模型和工具配置能接管旧的持久化 `/data` 文件。

如果你需要在运行态手工编辑 `/data/deer-flow/config.yaml` 并保留更改，应把 `DEER_FLOW_MANAGED_CONFIG=false`，同时自行负责配置漂移。

## 默认模型

`hfs/config/config.hfs.yaml` 当前第一模型为：

```yaml
name: longcat-flash-thinking-2601
display_name: LongCat Flash Thinking 2601
use: langchain_openai:ChatOpenAI
model: longcat-flash-thinking-2601
api_key: $OPENAI_API_KEY
base_url: https://gateway.ai.cloudflare.com/v1/98e18e2c295c6564954400ea5502d9f2/open/custom-hf/v2
supports_thinking: true
```

这里的 `OPENAI_API_KEY` 实际作为 Cloudflare AI Gateway bearer token 使用。`base_url` 填到 `/v2`，由 LangChain/OpenAI-compatible client 拼接 `/chat/completions`。

## Ops 服务

`hfs/services/ops_service.py` 是只读诊断服务：

- `/_ops/healthz`：公开，返回 coarse ops service 存活状态，不返回 upstream SHA 或文件路径。
- `/_ops/readyz`：公开，返回 coarse readiness 和各检查项名称/status，不返回内部路径、错误详情或 upstream SHA。
- `/_ops/status`：需要 `Authorization: Bearer $DEER_FLOW_OPS_TOKEN`，返回详细 readiness、upstream SHA 和 supervisor status。
- `/_ops/health`：需要 token，返回详细 readiness，HTTP 状态随 readiness 变化。
- `/_ops/system`：需要 token，返回 Python/runtime、内存和磁盘摘要。
- `/_ops/persistence`：需要 token，检查 `$DEER_FLOW_HOME`、SQLite 目录/文件、日志、run 目录和持久化探针，并把 `users/` 与旧目录作为观察项返回。
- `/_ops/version`：需要 token，返回 wrapper service、Space metadata 和上游 DeerFlow SHA/ref/version。
- `/_ops/metrics`：需要 token，返回 Prometheus text exposition。
- `/_ops/logs`：需要 token，只能读取 allowlist 中的日志目标，不能按请求读取任意路径；输出会 redaction 已知 secret 值。
- `/_ops/errors`：需要 token，从 allowlist 日志 tail 中按固定错误模式聚合。
- `/_ops/config`：需要 token，返回白名单环境变量和 secret presence，不返回 secret 值。

Ops 服务不提供命令执行、不读取任意文件、不接受用户自定义检查命令。浏览器 shell 不把 token 写入 `localStorage`；使用 token header 成功认证后可签发 path-scoped、`HttpOnly`、`SameSite=Strict` session cookie。query string 不接受 token。

## Admin 服务

`hfs/services/admin_service.py` 是受限管理服务：

- `/_admin/`：公开浏览器 shell，用于输入 `DEER_FLOW_ADMIN_TOKEN` 并调用受保护 API；shell 本身不得泄露 secret、配置值或管理能力。
- `/_admin/api/status`：默认由 `DEER_FLOW_ADMIN_ENABLED=false` 关闭；维护窗口启用后需要 token，返回 admin 状态和 supervisor 进程状态。
- `/_admin/api/config`：默认关闭；维护窗口启用后需要 token，返回安全配置和 secret presence。
- `/_admin/api/actions`：默认关闭；维护窗口启用后需要 token，返回当前允许的 read-only/write action 清单。
- `/_admin/api/audit`：默认关闭；维护窗口启用后需要 token，读取 `admin-actions.jsonl` 的最近事件。
- `/_admin/api/actions/run-health-checks`：默认关闭；维护窗口启用后需要 token、intent 和 confirm header，执行只读 Nginx config test 与 supervisor status 检查。
- `/_admin/api/reload-nginx`：固定动作，只有 `DEER_FLOW_ADMIN_ACTIONS_ENABLED=true` 时可用。
- `/_admin/api/restart`：固定 supervisor restart，仅允许 `gateway`、`frontend`、`nginx`。

默认应保持：

```bash
DEER_FLOW_ADMIN_ENABLED=false
DEER_FLOW_ADMIN_ACTIONS_ENABLED=false
```

没有 web terminal、SSH、tunnel、任意命令执行入口。

## Sandbox profile

默认配置：

```yaml
sandbox:
  use: deerflow.sandbox.local:LocalSandboxProvider
  allow_host_bash: false
```

工具组默认偏保守：`web` 和 `file:read`。不启用 `file:write`、`bash`、Docker sandbox 或 Kubernetes provisioner。

## 数据与持久化

运行态数据位于：

```text
/data/deer-flow
├─ data/deerflow.db
├─ users/<user-id>/...
├─ logs/
└─ generated secrets
```

建议给 HF Space 绑定持久化 Storage 到 `/data`。否则账号、thread/checkpointer 数据、uploads、memory、生成 secret 和运行态 config 会随 Space 重建或迁移丢失。当前 live Space 尚未挂载 Storage，因此代码路径已经指向 `/data` 不等于跨 rebuild 已持久化。

## 升级建议

1. 刷新上游并把 `DEERFLOW_REF` 更新到经过本仓验证的精确 commit SHA；不要用浮动 `main` 发布。
2. 推送 GitHub 和 HF。
3. 等 HF runtime `raw.sha` 与 `hf/main` 对齐。
4. 检查 `/health`、`/_ops/readyz`、`/_ops/version`、`/openapi.json`、`/api/v1/auth/setup-status`，并核对 upstream SHA。
5. 登录浏览器，检查 `/api/models` 和一条真实 chat。
6. 最后再调整 Space 可见性或扩大使用范围。
