---
title: DeerFlow-all-in-one-HFS
emoji: 🦌
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
suggested_hardware: cpu-upgrade
pinned: false
license: gpl-3.0
---

# DeerFlow-all-in-one-HFS

`DeerFlow-all-in-one-HFS` 是把 [ByteDance DeerFlow](https://github.com/bytedance/deer-flow) 部署到 Hugging Face Docker Space 的根级包装仓库。仓库根目录就是 Hugging Face Space 的部署源；`local/` 只作为本机参考材料，不参与构建、提交或云端部署。

## HFS 范式定位

本仓库按 `/Users/sky/Github/SKY-Prompt/hfs-dev` 的 Pattern A 对齐：它维护的是上游 DeerFlow 在 HFS 上的可运行交付包，而不是 DeerFlow 产品源码本身。因此仓库根目录必须同时作为 Hugging Face Space root 和 GitHub 维护根，不能再套一层 `cloud/hfs/`。

runtime 获取模式是 `source-fetch`：Docker build 阶段通过 `DEERFLOW_REPO` / `DEERFLOW_REF` 拉取上游源码。`DEERFLOW_REF=main` 只适合开发默认值；发布态或长期运行的 demo 应传入已验证的上游 commit SHA。对齐声明见 [hfs-dev.toml](hfs-dev.toml)，其中 v2 `[[release_pins]]` 把 `DEERFLOW_REF` 标为必须使用 commit SHA 的 release pin。

当前线上目标：

| 项 | 地址 |
|---|---|
| GitHub | https://github.com/BlueSkyXN/DeerFlow-all-in-one-HFS |
| Hugging Face Space | https://huggingface.co/spaces/BlueSkyXN/DeerFlow-all-in-one-HFS |
| App URL | https://blueskyxn-deerflow-all-in-one-hfs.hf.space |

## 当前状态

已验证的 v0 运行形态：

- Hugging Face Docker Space 单容器运行，公网只暴露 `7860`。
- Nginx 统一代理 DeerFlow frontend、Gateway、ops 和 admin。
- Docker build 阶段从 `bytedance/deer-flow` 拉取上游源码。
- 前端使用 `next build --webpack` 构建，runtime 使用 `pnpm start`，不再使用 Next dev server。
- Gateway 使用 `uvicorn app.gateway.app:app --host 127.0.0.1 --port 8001`。
- 默认模型为 Cloudflare AI Gateway OpenAI-compatible endpoint 上的 `longcat-flash-thinking-2601`。
- `DEER_FLOW_MANAGED_CONFIG=true` 时，启动时会用 `hfs/config/config.hfs.yaml` 覆盖运行态 `/data/deer-flow/config.yaml`，避免旧持久化配置继续生效。
- `/setup` 初始化管理员流程、登录态 `/api/models`、真实 chat 调用和 token usage 已通过浏览器验证。

## 进程与端口

```text
Hugging Face Docker Space
└─ container
   ├─ nginx                         0.0.0.0:7860
   ├─ DeerFlow frontend / Next.js   127.0.0.1:3000
   ├─ DeerFlow Gateway / FastAPI    127.0.0.1:8001
   ├─ HFS ops service               127.0.0.1:8081
   └─ HFS admin service             127.0.0.1:8082
```

## 关键路由

| 路径 | 说明 |
|---|---|
| `/` | DeerFlow 首页和应用入口。 |
| `/setup` | 首次启动管理员初始化页。 |
| `/workspace` | 登录后工作区。 |
| `/health` | DeerFlow Gateway 健康检查。 |
| `/openapi.json` | Gateway OpenAPI schema。 |
| `/api/v1/auth/setup-status` | 公开 first-boot setup 状态。 |
| `/api/models` | 登录态模型列表。 |
| `/api/sandboxes` | HFS demo 中故意返回 `404`，不启用 sandbox provisioner。 |
| `/_ops/healthz` | 公开 ops 存活检查。 |
| `/_ops/readyz` | 公开综合 readiness 检查。 |
| `/_ops/status` | 需要 `DEER_FLOW_OPS_TOKEN` 的 supervisor/readiness 状态。 |
| `/_ops/config` | 需要 `DEER_FLOW_OPS_TOKEN` 的安全配置和 secret presence 视图。 |
| `/_admin/` | 公开浏览器管理 shell；仅用于输入 tab-local token 和触发受保护 API，本身不得泄露 secret、配置值或写动作能力。 |
| `/_admin/api/status` | admin API，默认由 `DEER_FLOW_ADMIN_ENABLED=false` 关闭；维护窗口启用后仍需要 `DEER_FLOW_ADMIN_TOKEN`。 |

## 必需配置

推荐在 Hugging Face Space Settings 中配置 Variables 和 Secrets。不要把真实值写入仓库、README、docs、issue、PR 或日志截图。

推荐 Variables：

```bash
DEER_FLOW_ENV=hf-space
DEER_FLOW_PROJECT_ROOT=/home/user/app/deer-flow
DEER_FLOW_HOME=/data/deer-flow
DEER_FLOW_CONFIG_PATH=/data/deer-flow/config.yaml
DEER_FLOW_EXTENSIONS_CONFIG_PATH=/data/deer-flow/extensions_config.json
DEER_FLOW_SKILLS_PATH=/home/user/app/deer-flow/skills
DEER_FLOW_MANAGED_CONFIG=true
GATEWAY_WORKERS=1
GATEWAY_ENABLE_DOCS=true
GATEWAY_CORS_ORIGINS=https://blueskyxn-deerflow-all-in-one-hfs.hf.space
HF_HOME=/data/hf
DEER_FLOW_OPS_PORT=8081
DEER_FLOW_ADMIN_PORT=8082
DEER_FLOW_ADMIN_ENABLED=false
DEER_FLOW_ADMIN_ACTIONS_ENABLED=false
```

推荐 Secrets：

```bash
OPENAI_API_KEY=<cloudflare-ai-gateway-bearer-token>
BETTER_AUTH_SECRET=<long-random-secret>
DEER_FLOW_INTERNAL_AUTH_TOKEN=<long-random-token>
DEER_FLOW_OPS_TOKEN=<ops-token>
DEER_FLOW_ADMIN_TOKEN=<admin-token>
```

`OPENAI_API_KEY` 在当前 HFS 配置中作为 Cloudflare AI Gateway bearer token 使用。默认模型配置见 [hfs/config/config.hfs.yaml](hfs/config/config.hfs.yaml)。

## 本地快速启动

```bash
cp examples/local.env.example .env.local
# 编辑 .env.local，至少配置 OPENAI_API_KEY 才能跑真实 chat。
make build
make run
```

烟测：

```bash
make smoke
```

本地运行会把 `./.data` 挂载到容器 `/data`，可用 `make clean` 清理。

## 部署到 GitHub 和 HF

```bash
git push origin main
git remote add hf https://huggingface.co/spaces/BlueSkyXN/DeerFlow-all-in-one-HFS 2>/dev/null || true
git push hf main
```

部署后确认 HF runtime 的 `runtime.raw.sha` 与 `hf/main` 对齐，再做 smoke：

```bash
BASE=https://blueskyxn-deerflow-all-in-one-hfs.hf.space
curl -fsS "$BASE/_ops/readyz"
curl -fsS "$BASE/health"
curl -fsS "$BASE/api/v1/auth/setup-status"
```

带 token 的状态检查：

```bash
curl -H "Authorization: Bearer $DEER_FLOW_OPS_TOKEN" \
  https://blueskyxn-deerflow-all-in-one-hfs.hf.space/_ops/status

# 只有在维护窗口显式设置 DEER_FLOW_ADMIN_ENABLED=true 时才检查 admin API。
curl -H "Authorization: Bearer $DEER_FLOW_ADMIN_TOKEN" \
  https://blueskyxn-deerflow-all-in-one-hfs.hf.space/_admin/api/status
```

## 文档索引

- [docs/architecture.md](docs/architecture.md)：单容器架构、进程模型、路由和数据布局。
- [docs/deployment.md](docs/deployment.md)：HF Space 部署步骤和验收清单。
- [docs/configuration.md](docs/configuration.md)：Variables、Secrets 和 `.env.local` 分层。
- [docs/development.md](docs/development.md)：本地 Docker 构建、运行和 smoke。
- [docs/upstream-mapping.md](docs/upstream-mapping.md)：与 DeerFlow 官方部署形态的映射。
- [docs/security.md](docs/security.md)：安全边界、禁用项和 public Space checklist。
- [docs/ops-runbook.md](docs/ops-runbook.md)：常见故障和定位方式。

## License

本仓库保留根目录现有 license 文件。上游 DeerFlow 的授权以 [bytedance/deer-flow](https://github.com/bytedance/deer-flow) 为准。
