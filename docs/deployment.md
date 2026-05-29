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

发布态 build pin：

```bash
DEERFLOW_REF=<deer-flow-upstream-commit-sha>
```

`DEERFLOW_REF=main` 仅用于开发迭代。提交到长期运行的 HF Space 前，应把它设为已验证的 DeerFlow upstream commit SHA；HF Docker Space 会把 Variables 作为 Docker build args 传入 `Dockerfile ARG`。

## 5. Secrets

当前默认模型走 Cloudflare AI Gateway，Secret 名沿用 OpenAI-compatible client 的 `OPENAI_API_KEY`：

```bash
OPENAI_API_KEY=<cloudflare-ai-gateway-bearer-token>
```

推荐固定 secret：

```bash
BETTER_AUTH_SECRET=<long-random-secret>
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
- auth/session 相关持久状态
- `threads/`
- `uploads/`
- `logs/`
- generated secrets，前提是没有通过 HF Secrets 显式提供

如果没有持久化存储，Space 重启后这些状态可能丢失。

## 7. 首次启动

启动时 `hfs/bin/entrypoint.sh` 会：

1. 检查 `/data/deer-flow` 是否可写，不可写则退回 `/tmp/deer-flow`。
2. 导出 DeerFlow 路径、Gateway URL、provider key 占位值。
3. 在 `DEER_FLOW_MANAGED_CONFIG=true` 时同步 `hfs/config/config.hfs.yaml` 到 `DEER_FLOW_CONFIG_PATH`。
4. 创建 `extensions_config.json`。
5. 在未提供 `BETTER_AUTH_SECRET` / `DEER_FLOW_INTERNAL_AUTH_TOKEN` 时生成临时或持久 secret。
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
