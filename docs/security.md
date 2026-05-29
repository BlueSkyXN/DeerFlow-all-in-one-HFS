# Security Notes

## 定位

本项目是 DeerFlow on Hugging Face Space 的 demo / proof-of-concept 包装，不是生产多租户部署。

默认安全目标：能公开访问基础 UI，但不暴露任意命令执行、Docker socket、Kubernetes provisioner 或 web terminal。

## 默认安全姿态

`hfs/config/config.hfs.yaml` 默认：

```yaml
sandbox:
  use: deerflow.sandbox.local:LocalSandboxProvider
  allow_host_bash: false

uploads:
  auto_convert_documents: false

tool_groups:
  - name: web
  - name: file:read
```

默认不启用：

- `bash` tool。
- `file:write` tool group。
- Docker sandbox。
- Kubernetes provisioner。
- `/api/sandboxes` provisioner route。
- web terminal。
- SSH。
- tunnel。
- 任意用户输入命令执行面。

## Auth 和 CSRF

DeerFlow Gateway 对非公开 API 有 auth middleware。首次管理员初始化走 `/setup` 和 `/api/v1/auth/initialize`。

`GATEWAY_CORS_ORIGINS` 必须包含当前浏览器 origin，例如：

```bash
GATEWAY_CORS_ORIGINS=https://blueskyxn-deerflow-all-in-one-hfs.hf.space
```

否则 auth POST 会被 CSRF middleware 拦截，报：

```text
Cross-site auth request denied.
```

Nginx 需要正确传递 `X-Forwarded-Proto` 和 `X-Forwarded-Host`，当前 `hfs/nginx/nginx.conf` 已处理 HF proxy 场景。

## Ops routes

公开：

```text
/_ops/healthz
/_ops/readyz
```

需要 `DEER_FLOW_OPS_TOKEN`：

```text
/_ops/status
/_ops/config
```

`/_ops/config` 只返回白名单配置和 secret presence，不返回 secret 值。

Nginx 对 `/_ops/*` 只允许 `GET`，并把 request body limit 收窄到 `16k`，避免公开诊断面继承上传接口的 100M 限制。

## Admin routes

公开 HTML shell：

```text
/_admin/
```

`/_admin/` 可以公开路由，但它只是 token 输入和 API 调用 shell；默认不得返回 secret、完整配置、进程详情或任何写能力。

默认 `DEER_FLOW_ADMIN_ENABLED=false`，admin API 关闭，只保留 HTML shell。维护窗口显式启用后，API 仍需要 `DEER_FLOW_ADMIN_TOKEN`：

```text
/_admin/api/status
/_admin/api/config
/_admin/api/reload-nginx
/_admin/api/restart
```

写动作默认由 `DEER_FLOW_ADMIN_ACTIONS_ENABLED=false` 关闭；维护窗口确需启用时，还需要：

```bash
DEER_FLOW_ADMIN_ACTIONS_ENABLED=true
```

默认应保持：

```bash
DEER_FLOW_ADMIN_ENABLED=false
DEER_FLOW_ADMIN_ACTIONS_ENABLED=false
```

写动作还需要 `X-DeerFlow-Admin-Intent: DeerFlow-HFS-Admin` 和精确的 `X-DeerFlow-Admin-Confirm` header，并会写入 `/data/deer-flow/logs/admin-actions.jsonl` 审计记录。

Nginx 对 `/_admin/*` 只允许 `GET` / `POST`，并把 request body limit 收窄到 `64k`。公开 HTML shell 不持久化 admin token 到 browser storage。

Admin restart 仅允许固定服务：

```text
gateway
frontend
nginx
```

没有任意 service 名称，没有 shell command 输入。

## 模型和费用风险

当前默认模型通过 Cloudflare AI Gateway 调用 `longcat-flash-thinking-2601`。公网 Space 配模型 key 后会产生模型费用或额度消耗。

建议：

- Space 保持 Private 或 Protected，除非已做好成本控制。
- API key 使用低权限、低额度、可快速轮换的 demo key。
- provider 侧设置预算上限。
- 管理员密码使用强密码。
- 不在日志或截图中暴露 token。

## Secrets

应放入 HF Secrets：

```bash
OPENAI_API_KEY
OPENROUTER_API_KEY
BETTER_AUTH_SECRET
DEER_FLOW_INTERNAL_AUTH_TOKEN
DEER_FLOW_OPS_TOKEN
DEER_FLOW_ADMIN_TOKEN
TAVILY_API_KEY
SERPER_API_KEY
JINA_API_KEY
EXA_API_KEY
FIRECRAWL_API_KEY
INFOQUEST_API_KEY
```

不要放入：

- `hfs/config/config.hfs.yaml`
- `.env` / committed env files
- README
- docs
- PR 文案
- issue
- test snapshot
- public screenshots

## Uploads

默认 `auto_convert_documents=false`。启用文档转换会扩大解析器攻击面，也会增加 CPU/内存消耗。只建议在可信用户、私有 Space 中启用。

## Public Space checklist

公开前确认：

- `/api/sandboxes` 返回 404。
- `allow_host_bash: false`。
- 未启用 `bash` tool。
- 未启用不受控 `file:write`。
- `DEER_FLOW_ADMIN_ACTIONS_ENABLED=false`。
- `GATEWAY_CORS_ORIGINS` 只包含可信 origin。
- 管理员密码足够强。
- 模型 provider key 有预算上限。
- `BETTER_AUTH_SECRET` 和 `DEER_FLOW_INTERNAL_AUTH_TOKEN` 是稳定 secret。
- `/data` 已持久化或明确接受重启丢状态。
