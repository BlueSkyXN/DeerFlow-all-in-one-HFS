# Local Test

## 前提

- Docker with BuildKit。
- 能访问 GitHub、PyPI、npm registry、ghcr.io。
- 如需真实 chat，需要可用的 OpenAI-compatible API token。当前 HFS 默认把 `OPENAI_API_KEY` 当作 Cloudflare AI Gateway bearer token。

## 准备本地 env

```bash
cp examples/local.env.example .env.local
```

至少填写：

```bash
OPENAI_API_KEY=<cloudflare-ai-gateway-bearer-token>
AUTH_JWT_SECRET=<local-secret>
DEER_FLOW_INTERNAL_AUTH_TOKEN=<local-token>
DEER_FLOW_OPS_TOKEN=<local-ops-token>
DEER_FLOW_ADMIN_TOKEN=<local-admin-token>
```

本地默认 `GATEWAY_CORS_ORIGINS=http://localhost:7860`，`DEER_FLOW_TRUSTED_ORIGINS` 使用相同 origin。

## 构建

```bash
make build
```

Docker build 会先运行 `pnpm typecheck`，再加载 HFS Next config overlay 执行 webpack production build。这个拆分用于避免 HF `cpu-basic` 在 Webpack graph 与 TypeScript program 同时驻留时被 OOM kill；typecheck 失败仍会直接终止构建。

等价命令：

```bash
docker build \
  --build-arg DEERFLOW_REF=964162747f4839a954e247bef82f5f69dde8219d \
  -t deerflow-all-in-one-hfs .
```

可 pin 上游 DeerFlow：

```bash
docker build \
  --build-arg DEERFLOW_REF=<commit-sha> \
  -t deerflow-all-in-one-hfs:<commit-sha> .
```

## 运行

```bash
make run
```

等价命令：

```bash
mkdir -p .data
docker run --rm -it \
  -p 7860:7860 \
  --env-file .env.local \
  -v "$PWD/.data:/data" \
  deerflow-all-in-one-hfs
```

打开：

```text
http://localhost:7860
http://localhost:7860/setup
```

## Smoke

```bash
make smoke
```

脚本来源：`scripts/smoke-test.sh`。检查项：

- `/health` -> 200
- `/nginx-health` -> 200
- `/healthz` -> 200
- `/openapi.json` -> 200
- `/api/v1/auth/setup-status` -> 200，且 `registration_enabled=false`
- `/api/sandboxes` -> 404
- `/_ops/healthz` -> 200
- `/_ops/readyz` -> 200
- `/_admin/` -> 200
- `/_ops/status`、`/_ops/health`、`/_ops/system`、`/_ops/persistence`、`/_ops/version`、`/_ops/metrics`、`/_ops/errors` -> 200，仅当 shell 中存在 `DEER_FLOW_OPS_TOKEN` 或 `OPS_TOKEN`
- `/_admin/api/status`、`/_admin/api/actions`、`/_admin/api/audit`、`/_admin/api/actions/run-health-checks` -> 200，仅当 shell 中存在 `DEER_FLOW_ADMIN_TOKEN` / `ADMIN_TOKEN` 且 `DEER_FLOW_ADMIN_ENABLED=true`

## Static check

```bash
make static-check
```

该检查不需要 Docker 或 secrets，用于 PR 前快速验证：

- shell / Python 语法。
- ops/admin dependency-free service contract integration checks。
- Pattern A root layout 没有误迁到 `cloud/hfs/`。
- `README.md` metadata、`Dockerfile EXPOSE`、Nginx listen、healthcheck、smoke 端口一致。
- `hfs/` 内部路径、admin API/write actions 默认关闭、SHA pin、config v26、SQLite/JWT/persistence contract 一致。

## Shell

```bash
make shell
```

常用路径：

```text
/home/user/app/deer-flow
/home/user/app/hfs
/data/deer-flow
/data/deer-flow/data/deerflow.db
```

## 本地持久化数据

`make run` 默认挂载：

```text
./.data -> /data
```

清理本地运行态：

```bash
make clean
```

如果你启用了 `DEER_FLOW_MANAGED_CONFIG=true`，容器每次启动会用 `hfs/config/config.hfs.yaml` 覆盖 `.data/deer-flow/config.yaml`。

## 构建镜像源优化

npm mirror：

```bash
docker build \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
  -t deerflow-all-in-one-hfs .
```

PyPI mirror：

```bash
docker build \
  --build-arg UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  -t deerflow-all-in-one-hfs .
```

apt mirror：

```bash
docker build \
  --build-arg APT_MIRROR=mirrors.aliyun.com \
  -t deerflow-all-in-one-hfs .
```
