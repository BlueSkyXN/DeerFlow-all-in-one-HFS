# Deploy to Hugging Face Docker Space

## 1. 目标 Space

```text
Repo: https://huggingface.co/spaces/BlueSkyXN/DeerFlow-all-in-one-HFS
App : https://blueskyxn-deerflow-all-in-one-hfs.hf.space
```

仓库根目录的 `README.md` 带 Hugging Face Space card front matter：

```yaml
sdk: docker
app_port: 7860
```

HF 会用根目录 `Dockerfile` 构建镜像。

## 2. 推送代码

同一个提交应推送到 GitHub 和 HF Space：

```bash
git push origin main
git remote add hf https://huggingface.co/spaces/BlueSkyXN/DeerFlow-all-in-one-HFS 2>/dev/null || true
git push hf main
```

部署完成的判断不是 `git push` 成功，而是 HF runtime 的 `runtime.raw.sha` 与 `hf/main` 对齐且 `stage=RUNNING`。

## 3. 硬件建议

推荐起点：

- `cpu-upgrade`：构建和运行更稳。
- `cpu-basic`：可以运行，但 build 更慢。
- GPU：默认不需要，因为模型走外部 API。

当前 Docker build 会执行 `next build --webpack`。这是为了避免 Next dev server 在 HF 代理下导致 `/setup` hydration 卡死。

## 4. Variables

在 Space Settings -> Variables 添加：

```bash
DEER_FLOW_ENV=hf-space
DEER_FLOW_PROJECT_ROOT=/home/user/app/deer-flow
DEER_FLOW_HOME=/data/deer-flow
DEER_FLOW_DB_DIR=/data/deer-flow/data
DEER_FLOW_CONFIG_PATH=/data/deer-flow/config.yaml
DEER_FLOW_EXTENSIONS_CONFIG_PATH=/data/deer-flow/extensions_config.json
DEER_FLOW_SKILLS_PATH=/home/user/app/deer-flow/skills
DEER_FLOW_MANAGED_CONFIG=true
GATEWAY_WORKERS=1
GATEWAY_ENABLE_DOCS=true
GATEWAY_CORS_ORIGINS=https://blueskyxn-deerflow-all-in-one-hfs.hf.space
DEER_FLOW_TRUSTED_ORIGINS=https://blueskyxn-deerflow-all-in-one-hfs.hf.space
HF_HOME=/data/hf
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
```

发布态 build pin 不在 HF Variables 中配置，而是提交在 `Dockerfile ARG DEERFLOW_REF`。当前 pin 为 `0f0955bf7b2ae64ecb5099551b86049c2091a80a`，是 2026-07-25 release cut 时最新 `main` 的 `2.1.0` source candidate；最新正式 release 仍为 `v2.0.0`。HF Variables 不会自动变成 Docker build args。

## 5. Secrets

当前默认模型走 Cloudflare AI Gateway，Secret 名沿用 OpenAI-compatible client 的 `OPENAI_API_KEY`：

```bash
OPENAI_API_KEY=<cloudflare-ai-gateway-bearer-token>
```

推荐固定 secret：

```bash
AUTH_JWT_SECRET=<long-random-secret>
DEER_FLOW_INTERNAL_AUTH_TOKEN=<long-random-token>
DEER_FLOW_OPS_TOKEN=<ops-token>
DEER_FLOW_ADMIN_TOKEN=<admin-token>
```

可选 provider：

```bash
TAVILY_API_KEY=...
SERPER_API_KEY=...
JINA_API_KEY=...
EXA_API_KEY=...
FIRECRAWL_API_KEY=...
INFOQUEST_API_KEY=...
OPENROUTER_API_KEY=...
```

不要在公开文档、commit、PR 或日志中写真实 secret。

## 6. 持久化存储

建议绑定 HF Storage 到：

```text
/data
```

`/data/deer-flow` 中会保存：

- `config.yaml`
- `extensions_config.json`
- `data/deerflow.db`，包含账号、threads metadata、checkpointer 和应用数据库状态
- `.jwt_secret`，仅当未通过 HF Secret 提供 `AUTH_JWT_SECRET`
- `users/<user-id>/...` 下的用户、thread、upload 和 memory 数据
- `logs/`
- generated secrets，前提是没有通过 HF Secrets 显式提供

如果没有持久化存储，Space 重启后这些状态可能丢失。

## 7. 首次启动

启动时 `hfs/bin/entrypoint.sh` 会：

1. 检查 `/data/deer-flow` 是否可写，不可写则退回 `/tmp/deer-flow`。
2. 导出 DeerFlow 路径、Gateway URL、provider key 占位值。
3. 在 `DEER_FLOW_MANAGED_CONFIG=true` 时同步 `hfs/config/config.hfs.yaml` 到 `DEER_FLOW_CONFIG_PATH`。
4. 创建 `extensions_config.json`。
5. 在未提供 `AUTH_JWT_SECRET` / `DEER_FLOW_INTERNAL_AUTH_TOKEN` 时生成临时或持久 secret；旧 `BETTER_AUTH_SECRET` 只作 JWT secret 迁移输入。
6. 启动 supervisor。

首次访问：

```text
https://blueskyxn-deerflow-all-in-one-hfs.hf.space/setup
```

创建第一个管理员账号后进入 workspace。

## 8. 验收命令

公开端点：

```bash
BASE=https://blueskyxn-deerflow-all-in-one-hfs.hf.space
curl -fsS "$BASE/nginx-health"
curl -fsS "$BASE/healthz"
curl -fsS "$BASE/health"
curl -fsS "$BASE/_ops/healthz"
curl -fsS "$BASE/_ops/readyz"
curl -fsS "$BASE/openapi.json"
curl -fsS "$BASE/api/v1/auth/setup-status"
```

受保护端点：

```bash
curl -H "Authorization: Bearer $DEER_FLOW_OPS_TOKEN" \
  "$BASE/_ops/status"
curl -H "X-Ops-Token: $DEER_FLOW_OPS_TOKEN" \
  "$BASE/_ops/errors"
curl -H "X-Ops-Token: $DEER_FLOW_OPS_TOKEN" \
  "$BASE/_ops/version"

# 只有显式启用 DEER_FLOW_ADMIN_ENABLED=true 时才检查 admin API。
curl -H "Authorization: Bearer $DEER_FLOW_ADMIN_TOKEN" \
  "$BASE/_admin/api/status"
```

浏览器验收：

1. 打开 `/setup` 或 `/workspace`。
2. 完成管理员初始化或登录。
3. 确认模型选择器显示 `LongCat Flash Thinking 2601`。
4. 发送一条简单消息，例如 `请只回复 OK`。
5. 确认有模型响应和 token usage。

## 9. 常用 HF CLI

```bash
hf spaces info BlueSkyXN/DeerFlow-all-in-one-HFS --format json
hf spaces logs BlueSkyXN/DeerFlow-all-in-one-HFS -n 300
hf spaces logs BlueSkyXN/DeerFlow-all-in-one-HFS --build -n 300
hf spaces variables list BlueSkyXN/DeerFlow-all-in-one-HFS
hf spaces secrets list BlueSkyXN/DeerFlow-all-in-one-HFS
```

## 10. 可见性建议

早期建议保持 Private 或 Protected。完全公开前至少确认：

- `OPENAI_API_KEY` 对应 provider 有预算上限。
- 管理员密码足够强。
- `DEER_FLOW_ADMIN_ACTIONS_ENABLED=false`。
- `/api/sandboxes` 返回 404。
- `allow_host_bash: false`。
- 未启用 `bash` 和 `file:write`。
