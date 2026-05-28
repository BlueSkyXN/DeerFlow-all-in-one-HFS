# DeerFlow-all-in-one-HFS v0 快速开发版记录

日期：2026-05-28

## 背景

本项目的目标是把 ByteDance `deer-flow` 包装成 Hugging Face Docker Space，可以在一个 HF Space 内运行 DeerFlow 前端、Gateway、运维诊断面和受限管理面。

`local/` 只作为本机参考材料，不作为部署来源，也不应进入云端构建上下文。当前根目录是可部署的 HFS 包装层，上游 DeerFlow 源码在 Docker build 阶段从 `https://github.com/bytedance/deer-flow.git` 拉取。

## 今天完成的事情

1. 将仓库根目录收敛为 HF Docker Space 部署包，避免依赖 `local/`。
2. 引入 `hfs/` 运行时封装：`entrypoint.sh`、`supervisord.conf`、`nginx.conf`、健康检查、ops 服务和 admin 服务。
3. 使用单容器多进程模型：Nginx 暴露 `7860`，内部运行 Gateway、Next frontend、ops 和 admin。
4. 引入 `.env.local` 作为本地环境变量台账；该文件只用于本机记录和手动同步 HF Variables/Secrets，不提交。
5. 增加 `examples/hf-space-variables.example.env`、`examples/hf-space-secrets.example.env` 和 `examples/local.env.example`，用于区分公开变量、密钥和本地记录。
6. 增加文档体系，覆盖架构、HF 部署、环境变量、安全边界、本地测试、故障排查和官方部署映射。
7. 针对 HF Space 页面加载问题，将前端从 upstream `pnpm dev` 升级为 Docker build 阶段 `next build --webpack`、runtime 阶段 `pnpm start`。

## 实现逻辑

HF Space 只暴露一个公网端口，所以本项目用 Nginx 做统一入口：

| 外部路径 | 内部服务 | 说明 |
| --- | --- | --- |
| `/`、`/setup`、`/workspace` | `127.0.0.1:3000` | DeerFlow Next.js 前端 |
| `/api/*` | `127.0.0.1:8001` | DeerFlow Gateway |
| `/health`、`/openapi.json` | `127.0.0.1:8001` | Gateway 健康和 API 文档 |
| `/_ops/*` | `127.0.0.1:8081` | 运维诊断面 |
| `/_admin/*` | `127.0.0.1:8082` | 受限管理面 |

Supervisor 负责拉起并守护所有内部进程，Docker HEALTHCHECK 调用 `hfs/healthcheck.sh` 检查公开就绪状态。

## v0 前端策略

最初为了避免 HF `cpu-basic` 上 `next build` 耗时过长，v0 使用 Next dev server 运行前端。

但 upstream `pnpm dev` 实际会启用 Next dev/HMR 链路。在当前 HF Space 代理环境里，浏览器访问 `/setup` 会停在 `Loading...`，Playwright 复现显示页面没有发出 `/api/v1/auth/setup-status` 请求，DOM 也没有 React hydration 痕迹，同时控制台持续出现 `/_next/webpack-hmr` WebSocket 错误。

短暂尝试 `pnpm exec next dev --webpack` 后，HF runtime 已接管新提交，但 `/setup` 仍停留在 `Loading...`，说明问题不是 Turbopack 单点，而是 Next dev server 在 HF 公网代理后的整体不可靠。

因此当前改为：

```bash
pnpm exec next build --webpack
pnpm start --hostname 127.0.0.1 --port 3000
```

这个方案仍是 v0 快速交付版，但前端运行方式必须按生产模式处理。它的目标是先保证 HF Space 上 setup 页面和基础 UI 可用，同时避开 dev HMR 在 HF 代理下的 hydration 风险。

Next 16 默认会对 dev/build 使用 Turbopack；HF `cpu-basic` 上 Turbopack production build 卡在优化阶段，因此当前显式使用 `--webpack`。后续优化方向是减少 Docker build 时间和镜像体积，而不是退回 dev server。验收标准仍是浏览器 smoke 和 `runtime.raw.sha` 对齐。

## ops 和 admin 边界

`/_ops/healthz` 和 `/_ops/readyz` 是公开健康检查。

`/_ops/status` 和 `/_ops/config` 需要 `DEER_FLOW_OPS_TOKEN`。

`/_admin/` 提供浏览器管理入口，`/_admin/api/*` 需要 `DEER_FLOW_ADMIN_TOKEN`。

`DEER_FLOW_ADMIN_ACTIONS_ENABLED=false` 是默认安全状态。当前没有 Web terminal、SSH、tunnel 或任意命令执行入口。

## env 对齐结论

`.env.local` 的定位是本地台账，不是云端部署文件。它应保持 gitignored，不应提交。

HF Variables 应包含非密钥配置，例如：

```text
DEER_FLOW_ENV
DEER_FLOW_PROJECT_ROOT
DEER_FLOW_HOME
DEER_FLOW_CONFIG_PATH
DEER_FLOW_EXTENSIONS_CONFIG_PATH
DEER_FLOW_SKILLS_PATH
DEER_FLOW_MANAGED_CONFIG
GATEWAY_WORKERS
GATEWAY_ENABLE_DOCS
GATEWAY_CORS_ORIGINS
HF_HOME
DEER_FLOW_OPS_PORT
DEER_FLOW_ADMIN_PORT
DEER_FLOW_ADMIN_ENABLED
DEER_FLOW_ADMIN_ACTIONS_ENABLED
```

HF Secrets 应包含密钥，例如：

```text
BETTER_AUTH_SECRET
DEER_FLOW_INTERNAL_AUTH_TOKEN
DEER_FLOW_OPS_TOKEN
DEER_FLOW_ADMIN_TOKEN
OPENROUTER_API_KEY
OPENAI_API_KEY
```

当前基础 UI 和 setup flow 不要求模型 provider key；真实 LLM 对话需要配置 `OPENAI_API_KEY`。本 HFS v0 默认将 `OPENAI_API_KEY` 用作 Cloudflare AI Gateway bearer token，并将第一模型配置为 `longcat-flash-thinking-2601`。

模型入口：

```text
base_url=https://gateway.ai.cloudflare.com/v1/98e18e2c295c6564954400ea5502d9f2/open/custom-hf/v2
model=longcat-flash-thinking-2601
```

`DEER_FLOW_MANAGED_CONFIG=true` 时，entrypoint 会在每次启动时用 `hfs/config.hfs.yaml` 覆盖 `DEER_FLOW_CONFIG_PATH`，确保旧 `/data/deer-flow/config.yaml` 不会继续保留 OpenRouter 默认模型。

`GATEWAY_CORS_ORIGINS` 必须包含当前 HF Space 公网 origin，否则初始化管理员、登录、注册等 auth POST 会被 DeerFlow 的 CSRF 防护拒绝，表现为 `Cross-site auth request denied.`。Nginx 也需要保留 HF 代理传入的 `X-Forwarded-Proto` 和 `X-Forwarded-Host`，避免后端把公网 HTTPS 请求误判成容器内 HTTP。

## 当前验收重点

1. HF runtime `stage` 为 `RUNNING`，且 `runtime.raw.sha` 与 HF repo `main` 对齐。
2. `/` 返回并渲染 DeerFlow 首页。
3. `/setup` 不再停留在 `Loading...`，应显示初始化管理员表单或已初始化后的登录/工作区跳转。
4. `/api/v1/auth/setup-status` 返回明确 JSON。
5. `/_ops/healthz`、`/_ops/readyz`、`/health`、`/openapi.json` 返回 `200`。
6. 受保护的 `/_ops/status` 和 `/_admin/api/status` 只能在带 token 时访问。
