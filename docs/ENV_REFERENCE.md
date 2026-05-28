# ENV Reference

本项目把环境变量分成三类：

- Hugging Face Variables：非敏感运行参数，可以在 Space Settings -> Variables 中配置。
- Hugging Face Secrets：API key、token、auth secret，只能放在 Space Settings -> Secrets。
- 本地 `.env.local`：本机私有台账，记录当前使用值、云端覆盖状态和 smoke 参数；必须保持 gitignored。

## 推荐 Variables

| Key | 推荐值 | 说明 |
|---|---|---|
| `DEER_FLOW_ENV` | `hf-space` | 标记当前运行环境。 |
| `DEER_FLOW_PROJECT_ROOT` | `/home/user/app/deer-flow` | 上游 DeerFlow 源码路径。 |
| `DEER_FLOW_HOME` | `/data/deer-flow` | 运行态数据路径，建议挂载 HF Storage。 |
| `DEER_FLOW_CONFIG_PATH` | `/data/deer-flow/config.yaml` | 首次启动由 `hfs/config.hfs.yaml` 复制生成。 |
| `DEER_FLOW_EXTENSIONS_CONFIG_PATH` | `/data/deer-flow/extensions_config.json` | MCP/skills 扩展配置。 |
| `DEER_FLOW_SKILLS_PATH` | `/home/user/app/deer-flow/skills` | 上游 skills 路径。 |
| `DEER_FLOW_MANAGED_CONFIG` | `true` | HFS 启动时用 `hfs/config.hfs.yaml` 覆盖运行态 config，确保模型/env 改动能接管旧 `/data` 配置。 |
| `GATEWAY_WORKERS` | `1` | CPU Space 默认单 worker。 |
| `GATEWAY_ENABLE_DOCS` | `true` | 暴露 `/docs`、`/redoc`、`/openapi.json`。 |
| `GATEWAY_CORS_ORIGINS` | `https://blueskyxn-deerflow-all-in-one-hfs.hf.space` | 允许浏览器从 HF 公网 origin 发起 auth 初始化、登录、注册等写 cookie 请求。 |
| `HF_HOME` | `/data/hf` | Hugging Face/cache 路径。 |
| `DEER_FLOW_OPS_PORT` | `8081` | 内部 ops service 端口。 |
| `DEER_FLOW_ADMIN_PORT` | `8082` | 内部 admin service 端口。 |
| `DEER_FLOW_ADMIN_ENABLED` | `true` | 启用 token-protected admin UI/API。 |
| `DEER_FLOW_ADMIN_ACTIONS_ENABLED` | `false` | 默认禁用 reload/restart 等写动作。 |
| `DEERFLOW_REF` | `main` 或 commit SHA | 上游 DeerFlow 构建版本。生产化建议 pin SHA。 |

## 推荐 Secrets

| Key | 必需性 | 说明 |
|---|---|---|
| `OPENAI_API_KEY` | 必需 | 当前 HFS 默认用作 Cloudflare AI Gateway bearer token。 |
| `OPENROUTER_API_KEY` | 可选 | 仅在你手动改回 OpenRouter 模型配置时使用。 |
| `BETTER_AUTH_SECRET` | 推荐 | DeerFlow auth/session secret。 |
| `DEER_FLOW_INTERNAL_AUTH_TOKEN` | 推荐 | Frontend 到 Gateway 的内部认证 token。 |
| `DEER_FLOW_OPS_TOKEN` | 推荐 | 访问 `/_ops/status`、`/_ops/config`。 |
| `DEER_FLOW_ADMIN_TOKEN` | 推荐 | 访问 `/_admin/api/*`。 |
| `TAVILY_API_KEY` | 可选 | Tavily search provider。 |
| `SERPER_API_KEY` | 可选 | Serper search provider。 |
| `JINA_API_KEY` | 可选 | Jina fetch provider。 |
| `EXA_API_KEY` | 可选 | Exa provider。 |
| `FIRECRAWL_API_KEY` | 可选 | Firecrawl provider。 |
| `INFOQUEST_API_KEY` | 可选 | InfoQuest provider。 |

## 本地 `.env.local` 台账建议

本地 `.env.local` 不提交，但建议保留以下分组：

```bash
# [HF_SPACE]
HF_SPACE_ID=BlueSkyXN/DeerFlow-all-in-one-HFS
HF_SPACE_URL=https://blueskyxn-deerflow-all-in-one-hfs.hf.space

# [VARIABLES]
DEER_FLOW_ENV=hf-space
DEER_FLOW_HOME=/data/deer-flow
DEER_FLOW_MANAGED_CONFIG=true
GATEWAY_CORS_ORIGINS=https://blueskyxn-deerflow-all-in-one-hfs.hf.space
DEER_FLOW_ADMIN_ENABLED=true
DEER_FLOW_ADMIN_ACTIONS_ENABLED=false

# [SECRETS]
OPENROUTER_API_KEY=...
OPENAI_API_KEY=...
BETTER_AUTH_SECRET=...
DEER_FLOW_INTERNAL_AUTH_TOKEN=...
DEER_FLOW_OPS_TOKEN=...
DEER_FLOW_ADMIN_TOKEN=...

# [LOCAL_SMOKE]
SMOKE_BASE_URL=https://blueskyxn-deerflow-all-in-one-hfs.hf.space
```

不要把 `.env.local`、真实 key、token、HF/GitHub token、个人信息写进 commit、README、issue、PR 或日志截图。
