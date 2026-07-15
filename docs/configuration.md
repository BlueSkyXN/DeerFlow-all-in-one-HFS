# ENV Reference

本项目把环境变量分成三层：

- Hugging Face Variables：非敏感运行参数。
- Hugging Face Secrets：API key、token、session secret。
- 本地 `.env.local`：本机私有台账，必须 gitignored。

不要把真实 key、token、密码、内部 URL 或个人信息写入 commit、README、docs、issue、PR、截图或公开日志。

## Hugging Face Variables

| Key | 推荐值 | 说明 |
|---|---|---|
| `DEER_FLOW_ENV` | `hf-space` | 标记运行环境。 |
| `DEER_FLOW_PROJECT_ROOT` | `/home/user/app/deer-flow` | Docker build 中拉取的上游 DeerFlow 路径。 |
| `DEER_FLOW_HOME` | `/data/deer-flow` | 运行态数据目录。 |
| `DEER_FLOW_DB_DIR` | `/data/deer-flow/data` | 统一 SQLite 数据库目录；managed config 通过 `$DEER_FLOW_DB_DIR` 引用。 |
| `DEER_FLOW_CONFIG_PATH` | `/data/deer-flow/config.yaml` | DeerFlow runtime config。 |
| `DEER_FLOW_EXTENSIONS_CONFIG_PATH` | `/data/deer-flow/extensions_config.json` | MCP/extensions config。 |
| `DEER_FLOW_SKILLS_PATH` | `/home/user/app/deer-flow/skills` | 上游 DeerFlow skills 路径。 |
| `DEER_FLOW_MANAGED_CONFIG` | `true` | 启动时用 `hfs/config/config.hfs.yaml` 覆盖 runtime config。 |
| `GATEWAY_WORKERS` | `1` | Gateway worker 数，CPU Space 推荐 1。 |
| `GATEWAY_ENABLE_DOCS` | `true` | 开启 `/docs`、`/redoc`、`/openapi.json`。 |
| `GATEWAY_CORS_ORIGINS` | `https://blueskyxn-deerflow-all-in-one-hfs.hf.space` | 允许 auth POST 的浏览器 origin。缺失会触发 `Cross-site auth request denied.`。 |
| `DEER_FLOW_TRUSTED_ORIGINS` | 与 `GATEWAY_CORS_ORIGINS` 相同 | frontend server-side origin 配置；当前 entrypoint 默认继承 Gateway allowlist。 |
| `HF_HOME` | `/data/hf` | Hugging Face/cache 路径。 |
| `DEER_FLOW_OPS_PORT` | `8081` | ops service 内部端口。 |
| `DEER_FLOW_OPS_SESSION_TTL_SECONDS` | `3600` | 使用 token header 认证后签发的 ops `HttpOnly` session TTL。 |
| `DEER_FLOW_OPS_COOKIE_SECURE` | `auto` | ops session cookie 的 `Secure` 策略；`auto` 根据 `X-Forwarded-Proto=https` 判断。 |
| `DEER_FLOW_OPS_DEFAULT_CHECKS_ENABLED` | `true` | 是否启用默认 gateway/frontend/config/persistence readiness checks。 |
| `DEER_FLOW_OPS_LOG_DIR` | `/data/deer-flow/logs` | 受限 ops log allowlist 的默认根目录。 |
| `DEER_FLOW_OPS_LOG_LINES_MAX` | `1000` | `/_ops/logs` 和 `/_ops/errors` 单次最大行数。 |
| `DEER_FLOW_OPS_LOG_TAIL_MAX_BYTES` | `1048576` | 单个日志文件 tail 读取的最大字节数。 |
| `DEER_FLOW_ADMIN_PORT` | `8082` | admin service 内部端口。 |
| `DEER_FLOW_ADMIN_ENABLED` | `false` | 是否启用 admin API。公开 demo 默认关闭；维护窗口才设为 true。 |
| `DEER_FLOW_ADMIN_ACTIONS_ENABLED` | `false` | 是否允许 reload/restart 固定写动作。默认 false。 |

`DEERFLOW_REF`、`APT_MIRROR`、`NPM_REGISTRY`、`UV_INDEX_URL` 是 Docker build args，不是 HF runtime Variables。Hugging Face Docker Space 不会把 Settings -> Variables 自动传给 `Dockerfile ARG`。发布 pin 必须提交在 Dockerfile 中；当前 pin 是 `45865e9f3f5ac1cd05bfce9406b30ea8da864c52`。本地可以通过 `make build DEERFLOW_REF=main` 临时覆盖。

## Hugging Face Secrets

| Key | 必需性 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | 必需 | 当前默认模型使用的 Cloudflare AI Gateway bearer token。 |
| `AUTH_JWT_SECRET` | 推荐 | 当前 Gateway 登录 session 的 JWT signing secret，应固定。未设置时 entrypoint 会在 `$DEER_FLOW_HOME/.jwt_secret` 生成。 |
| `BETTER_AUTH_SECRET` | 仅迁移 | 旧 HFS 配置兼容输入；仅当 `AUTH_JWT_SECRET` 缺失时映射过去，新部署不要继续使用。 |
| `DEER_FLOW_INTERNAL_AUTH_TOKEN` | 推荐 | frontend 到 Gateway 的内部认证 token，应固定。 |
| `DEER_FLOW_OPS_TOKEN` | 推荐 | 访问 `/_ops/status`、`/_ops/health`、`/_ops/system`、`/_ops/persistence`、`/_ops/version`、`/_ops/metrics`、`/_ops/logs`、`/_ops/errors` 和 `/_ops/config`。 |
| `DEER_FLOW_ADMIN_TOKEN` | 推荐 | 访问 `/_admin/api/*`。 |
| `OPENROUTER_API_KEY` | 可选 | 仅在你手动改用 OpenRouter 模型时需要。 |
| `TAVILY_API_KEY` | 可选 | Tavily search provider。 |
| `SERPER_API_KEY` | 可选 | Serper search provider。 |
| `JINA_API_KEY` | 可选 | Jina fetch provider。 |
| `EXA_API_KEY` | 可选 | Exa provider。 |
| `FIRECRAWL_API_KEY` | 可选 | Firecrawl provider。 |
| `INFOQUEST_API_KEY` | 可选 | InfoQuest provider。 |

## 默认模型配置

`hfs/config/config.hfs.yaml` 当前第一模型：

```yaml
name: longcat-flash-thinking-2601
display_name: LongCat Flash Thinking 2601
use: langchain_openai:ChatOpenAI
model: longcat-flash-thinking-2601
api_key: $OPENAI_API_KEY
base_url: https://gateway.ai.cloudflare.com/v1/98e18e2c295c6564954400ea5502d9f2/open/custom-hf/v2
request_timeout: 600.0
max_retries: 2
max_tokens: 8192
temperature: 0.7
supports_thinking: true
supports_vision: false
```

注意：`base_url` 是 OpenAI-compatible client 的 base URL，应停在 `/v2`，不要把 `/chat/completions` 写进 `base_url`。

## `.env.local` 台账建议

`.env.local` 只用于本机，不提交。

```bash
# [HF_SPACE]
HF_SPACE_ID=BlueSkyXN/DeerFlow-all-in-one-HFS
HF_SPACE_URL=https://blueskyxn-deerflow-all-in-one-hfs.hf.space

# [VARIABLES]
DEER_FLOW_ENV=hf-space
DEER_FLOW_HOME=/data/deer-flow
DEER_FLOW_DB_DIR=/data/deer-flow/data
DEER_FLOW_CONFIG_PATH=/data/deer-flow/config.yaml
DEER_FLOW_EXTENSIONS_CONFIG_PATH=/data/deer-flow/extensions_config.json
DEER_FLOW_SKILLS_PATH=/home/user/app/deer-flow/skills
DEER_FLOW_MANAGED_CONFIG=true
GATEWAY_CORS_ORIGINS=https://blueskyxn-deerflow-all-in-one-hfs.hf.space
DEER_FLOW_TRUSTED_ORIGINS=https://blueskyxn-deerflow-all-in-one-hfs.hf.space
DEER_FLOW_OPS_PORT=8081
DEER_FLOW_OPS_SESSION_TTL_SECONDS=3600
DEER_FLOW_OPS_COOKIE_SECURE=auto
DEER_FLOW_OPS_DEFAULT_CHECKS_ENABLED=true
DEER_FLOW_OPS_LOG_DIR=/data/deer-flow/logs
DEER_FLOW_OPS_LOG_LINES_MAX=1000
DEER_FLOW_OPS_LOG_TAIL_MAX_BYTES=1048576
DEER_FLOW_ADMIN_PORT=8082
DEER_FLOW_ADMIN_ENABLED=false
DEER_FLOW_ADMIN_ACTIONS_ENABLED=false

# [SECRETS]
OPENAI_API_KEY=...
AUTH_JWT_SECRET=...
DEER_FLOW_INTERNAL_AUTH_TOKEN=...
DEER_FLOW_OPS_TOKEN=...
DEER_FLOW_ADMIN_TOKEN=...

# [LOCAL_SMOKE]
SMOKE_BASE_URL=https://blueskyxn-deerflow-all-in-one-hfs.hf.space
```

## HF CLI 设置示例

Variables：

```bash
hf spaces variables add BlueSkyXN/DeerFlow-all-in-one-HFS -e DEER_FLOW_MANAGED_CONFIG=true
hf spaces variables add BlueSkyXN/DeerFlow-all-in-one-HFS -e GATEWAY_CORS_ORIGINS=https://blueskyxn-deerflow-all-in-one-hfs.hf.space
hf spaces variables add BlueSkyXN/DeerFlow-all-in-one-HFS -e DEER_FLOW_DB_DIR=/data/deer-flow/data
```

Secrets：

```bash
hf spaces secrets add BlueSkyXN/DeerFlow-all-in-one-HFS -s OPENAI_API_KEY=<token>
hf spaces secrets add BlueSkyXN/DeerFlow-all-in-one-HFS -s AUTH_JWT_SECRET=<long-random-secret>
hf spaces secrets add BlueSkyXN/DeerFlow-all-in-one-HFS -s DEER_FLOW_OPS_TOKEN=<token>
hf spaces secrets add BlueSkyXN/DeerFlow-all-in-one-HFS -s DEER_FLOW_ADMIN_TOKEN=<token>
```

## 变更生效规则

- HF Variables/Secrets 改动通常会触发 Space 重启。
- `hfs/config/config.hfs.yaml` 改动需要 push HF 并等待 rebuild。
- `DEER_FLOW_MANAGED_CONFIG=true` 会在启动时覆盖旧 `/data/deer-flow/config.yaml`。
- 如果设为 false，运行态 config 会成为 source of truth，仓库模板不再自动接管。
- Docker build pin 来自已提交的 `Dockerfile ARG DEERFLOW_REF=<commit-sha>`；HF runtime Variables 不能替代它。
