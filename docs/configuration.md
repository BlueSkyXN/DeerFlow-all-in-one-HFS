# ENV Reference

本项目把环境变量分成四层：

- 被忽略的 `.env`：HFS 同步的本地值账本；只在本机保存实际值，绝不提交或上传到文档。
- `.env.example`：公开键名模板，不含任何值；其键和分类必须与 `hfs-dev.toml` 一致。
- Hugging Face Variables / Secrets：远端运行设置，分别承载非敏感参数和 secret。
- `.env.local`：既有本地 Docker 运行兼容文件，`Makefile` 继续默认使用它，不是 HFS 同步输入。

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

`DEERFLOW_REF`、`APT_MIRROR`、`NPM_REGISTRY`、`UV_INDEX_URL` 是本地 build args，不是 HF runtime Variables。Hugging Face Docker Space 不会把 Settings -> Variables 自动传给 `Dockerfile ARG`。发布 pin 只由 `Dockerfile` 和 `Makefile` 的同一完整 SHA 维护，HFS v3 manifest 不重复登记它；本地可以通过 `make build DEERFLOW_REF=main` 临时覆盖。

## Managed config 安全与兼容默认

`hfs/config/config.hfs.yaml` 对齐上游 schema `config_version: 34`。HFS 显式固定 SQLite connection/checkpoint 默认、单节点 `agent_storage.backend: file`、当前 LLM retry 默认和 `authorization.enabled: false`；未显式写入的 v34 可选能力继续使用上游默认，不因此启用 plugins、远程 sandbox 或新的控制面。`auth.local.allow_registration: false` 会关闭公网自助注册，但不会阻止首次管理员通过 `/api/v1/auth/initialize` 初始化；`/api/v1/auth/setup-status` 应返回 `registration_enabled=false`。

## Hugging Face Secrets

| Key | 必需性 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | 必需 | 当前默认模型使用的 Cloudflare AI Gateway bearer token。 |
| `AUTH_JWT_SECRET` | 推荐 | 当前 Gateway 登录 session 的 JWT signing secret，应固定。未设置时 entrypoint 会在 `$DEER_FLOW_HOME/.jwt_secret` 生成。 |
| `BETTER_AUTH_SECRET` | 仅迁移 | 旧 HFS 配置兼容输入；仅当 `AUTH_JWT_SECRET` 缺失时映射过去，新部署不要继续使用。 |
| `DEER_FLOW_INTERNAL_AUTH_TOKEN` | 推荐 | frontend 到 Gateway 的内部认证 token，应固定。 |
| `OPS_TOKEN` | 推荐 | 访问 `/_ops/status`、`/_ops/health`、`/_ops/system`、`/_ops/persistence`、`/_ops/version`、`/_ops/metrics`、`/_ops/logs`、`/_ops/errors` 和 `/_ops/config`。 |
| `ADMIN_PASSWORD` | 推荐 | 访问 `/_admin/api/*`。 |
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

## HFS 值账本与本地兼容

先从公开模板创建本机 HFS 值账本，再仅在本机填入需要同步的值：

```bash
cp .env.example .env
```

`.env` 只供后续 HFS 同步使用；`hfs-dev.toml` 只登记 `local_only`、required `secrets`、`optional_secrets`、`variables` 四类键名，不含值。clean non-paid profile 只要求 auth/internal/ops 三个内部 Secret；admin、legacy migration、model 与 search provider key 保持 optional 且不配置。`local_only`（包括 build args、smoke aliases 和内部覆盖项）不得同步为 Space 设置。

本项目保持上游 YAML/JSON 与 env-driven 配置，不创建无意义的 `config.toml`，也没有需要分发的
seed。Settings 必须从忽略的本地 `.env` 事实源执行 `diff → push → readback`；candidate 和
production 使用独立 manifest，不能临时覆盖同一个 `space`：

```bash
python3 scripts/hf_space_sync.py diff --manifest hfs-dev.candidate.toml --env-file .env
python3 scripts/hf_space_sync.py push --manifest hfs-dev.candidate.toml --env-file .env
python3 scripts/hf_space_sync.py diff --manifest hfs-dev.candidate.toml --env-file .env
```

最后一次 `diff` 是 readback：Secret 只核名称，Variable 核值。清理窗口获批前不得使用
`--prune --yes`。旧 Ruijie wrapper 仅作为只读回退材料保留；取得 7 天无活动引用证据后，
再单独请求删除确认。

本地 Docker 开发仍使用既有模板和显式 `.env.local`：

```bash
cp examples/local.env.example .env.local
make run
```

不要以 `.env.local` 作为 HFS 的事实源，也不要把 `.env` 传给默认 `make run`。本轮不执行远端 Variables/Secrets 写入；远端对账、重建和 smoke 是后续发布门禁。

## 变更生效规则

- HF Variables/Secrets 的远端改动通常会触发 Space 重启；本轮没有执行这类写入。
- `hfs/config/config.hfs.yaml` 改动需要推送并等待远端 rebuild，属于后续门禁。
- `DEER_FLOW_MANAGED_CONFIG=true` 时，entrypoint **每次启动**都会覆盖 `$DEER_FLOW_CONFIG_PATH`（当前为 `/data/deer-flow/config.yaml`）；这是 wrapper-managed config，不登记 `seed_file` 或 mount config。
- 如果设为 false，运行态 config 会成为 source of truth，仓库模板不再自动接管，配置漂移由运行方负责。
- Docker build pin 来自已提交的 `Dockerfile ARG DEERFLOW_REF=<commit-sha>`，并由 `Makefile` 直接保持一致；HF runtime Variables 和 HFS v3 manifest 都不能替代或重复它。
