# Troubleshooting

## Space stuck at starting

检查：

- `README.md` front matter 中 `sdk: docker`。
- `README.md` front matter 中 `app_port: 7860`。
- 根目录存在 `Dockerfile`。
- Nginx 监听 `0.0.0.0:7860`。
- `/_ops/healthz` 通过 Nginx 返回 200。
- `/health` 通过 Nginx 返回 200。
- HF logs 中 supervisor 启动了 `gateway`、`frontend`、`ops`、`admin`、`nginx`。

命令：

```bash
hf spaces logs BlueSkyXN/DeerFlow-all-in-one-HFS -n 300
hf spaces logs BlueSkyXN/DeerFlow-all-in-one-HFS --build -n 300
```

## `/_ops/readyz` fails

`/_ops/readyz` 公开返回 coarse readiness，只暴露检查项名称和状态。具体检查包括：

- Gateway health。
- Frontend HTTP。
- Ops port。
- entrypoint 在 `DEER_FLOW_HOME` 写入的 persistence probe 存在。
- `DEER_FLOW_DB_DIR` 和 `deerflow.db` 存在。
- `DEER_FLOW_CONFIG_PATH` 存在。
- `DEER_FLOW_EXTENSIONS_CONFIG_PATH` 存在。

常见原因：

- Gateway 因 config schema 或 provider 配置启动失败。
- Frontend build 产物缺失，`pnpm start` 启动失败。
- `/data` 不可写。
- 首次启动仍在 warming up。

带 token 查看详细状态、具体错误、路径和 upstream SHA：

```bash
curl -H "Authorization: Bearer $DEER_FLOW_OPS_TOKEN" \
  https://blueskyxn-deerflow-all-in-one-hfs.hf.space/_ops/status
curl -H "X-Ops-Token: $DEER_FLOW_OPS_TOKEN" \
  https://blueskyxn-deerflow-all-in-one-hfs.hf.space/_ops/errors
curl -H "X-Ops-Token: $DEER_FLOW_OPS_TOKEN" \
  https://blueskyxn-deerflow-all-in-one-hfs.hf.space/_ops/version
```

## `/setup` 一直 Loading

历史原因是 HF 上运行 Next dev server，浏览器 hydration 不完成，并持续出现 HMR WebSocket 错误。

当前修复：

- Docker build 使用 `pnpm exec next build --webpack`。
- Runtime 使用 `pnpm start --hostname 127.0.0.1 --port 3000`。
- 不使用 `pnpm dev` 或 `next dev`。

如果再次出现：

1. 确认 runtime SHA 是最新提交。
2. 看 browser console 是否有 JS 错误。
3. 看 `/_ops/readyz` 的 `frontend_http`。
4. 看 HF runtime logs 中 frontend 是否 RUNNING。

## `Cross-site auth request denied.`

这是 DeerFlow CSRF middleware 拦截 auth POST。

检查：

```bash
GATEWAY_CORS_ORIGINS=https://blueskyxn-deerflow-all-in-one-hfs.hf.space
```

并确认 `hfs/nginx/nginx.conf` 传递：

```nginx
X-Forwarded-Host
X-Forwarded-Proto
```

验证方式：用同源 `Origin` POST `/api/v1/auth/initialize`，如果不再返回 403，而返回正常业务校验错误，例如 password too short，则 CSRF origin 问题已解决。

## `/health` fails

常见原因：

- `uv sync` build 失败。
- 上游 DeerFlow config schema 变化。
- `/data/deer-flow/config.yaml` 无效。
- `DEER_FLOW_MANAGED_CONFIG=false` 时旧 config 仍在生效。
- `uv run --no-sync` 找不到预构建 `.venv`。

建议先设：

```bash
DEER_FLOW_MANAGED_CONFIG=true
```

让 HFS 模板重新接管 runtime config。

如果 Gateway 能启动但账号或 thread 数据在 rebuild 后消失，检查 `/_ops/persistence` 中数据库是否位于 `/data/deer-flow/data/deerflow.db`，再用 `hf spaces volumes list` 确认 Space 是否真的挂载了 Storage。代码写入 `/data` 不能替代 Storage 配置。

## UI loads but chat fails

检查：

- 已完成 `/setup` 管理员初始化。
- 登录后 `/api/models` 返回模型列表。
- `OPENAI_API_KEY` 已配置为 HF Secret。
- `/api/models` 第一模型是 `longcat-flash-thinking-2601`。
- Cloudflare AI Gateway endpoint 可用。
- Provider quota/billing 正常。

当前默认 base URL：

```text
https://gateway.ai.cloudflare.com/v1/98e18e2c295c6564954400ea5502d9f2/open/custom-hf/v2
```

注意不要把 `/chat/completions` 写进 `base_url`。

## `/api/models` returns 401

这是正常现象：`/api/models` 需要登录态。

未登录 smoke 用：

```text
/health
/nginx-health
/healthz
/openapi.json
/api/v1/auth/setup-status
/_ops/healthz
/_ops/readyz
```

登录后可在浏览器里调用 `/api/models`。

## `/api/models` model 不对

如果仍显示 OpenRouter 或旧模型：

1. 确认 HF runtime SHA 已是最新。
2. 确认 `DEER_FLOW_MANAGED_CONFIG=true`。
3. 确认 `hfs/config/config.hfs.yaml` 第一模型是 `longcat-flash-thinking-2601`。
4. 重启 Space，让 entrypoint 覆盖 `/data/deer-flow/config.yaml`。

## Build stuck at `Creating an optimized production build ...`

Next 16 默认 Turbopack build 在 HF `cpu-basic` 上可能卡住。当前 Dockerfile 必须使用：

```bash
pnpm exec next build --webpack
```

不要改回 `pnpm build`，否则可能重新走 Turbopack。

## Build fails during `pnpm install`

可设置：

```bash
NPM_REGISTRY=https://registry.npmmirror.com
```

## Build fails during `uv sync`

可设置：

```bash
UV_INDEX_URL=https://pypi.org/simple
```

或区域镜像。如果上游 DeerFlow 新增 native dependency，可能需要在 Dockerfile 增加 apt package。

## `/_admin/api/*` returns 403

检查：

```bash
DEER_FLOW_ADMIN_ENABLED=true
DEER_FLOW_ADMIN_TOKEN=<secret>
```

写动作还需要：

```bash
DEER_FLOW_ADMIN_ACTIONS_ENABLED=true
```

只读 `/_admin/api/actions/run-health-checks` 不需要打开写动作开关，但仍需要 admin token、`X-DeerFlow-Admin-Intent: DeerFlow-HFS-Admin` 和 `X-DeerFlow-Admin-Confirm: run-health-checks`。

默认应该保持 false。

## `/api/sandboxes` returns 404

这是预期行为。HFS demo 不启用 Docker/Kubernetes sandbox provisioner。

## 需要文件写入或 bash

不要直接在公开 Space 中启用。建议路线：

1. 保持 Space Private。
2. 只增加必要的 `file:write` 工具。
3. 限定写入路径。
4. 仍保持 `bash` disabled。
5. 对不可信输入做单独验证。

## 需要 Docker/Kubernetes sandbox

本仓库不做 Docker-in-Docker 或 Docker socket 暴露。应使用外部 sandbox control plane，或改用官方 DeerFlow production deployment。
