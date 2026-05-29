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
BETTER_AUTH_SECRET=<local-secret>
DEER_FLOW_INTERNAL_AUTH_TOKEN=<local-token>
DEER_FLOW_OPS_TOKEN=<local-ops-token>
DEER_FLOW_ADMIN_TOKEN=<local-admin-token>
```

本地默认 `GATEWAY_CORS_ORIGINS=http://localhost:7860`。

## 构建

```bash
make build
```

等价命令：

```bash
docker build \
  --build-arg DEERFLOW_REF=main \
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
- `/openapi.json` -> 200
- `/api/v1/auth/setup-status` -> 200
- `/api/sandboxes` -> 404
- `/_ops/healthz` -> 200
- `/_ops/readyz` -> 200
- `/_admin/` -> 200
- `/_ops/status` -> 200，仅当 shell 中存在 `DEER_FLOW_OPS_TOKEN` 或 `OPS_TOKEN`
- `/_admin/api/status` -> 200，仅当 shell 中存在 `DEER_FLOW_ADMIN_TOKEN` / `ADMIN_TOKEN` 且 `DEER_FLOW_ADMIN_ENABLED=true`

## Static check

```bash
make static-check
```

该检查不需要 Docker 或 secrets，用于 PR 前快速验证：

- shell / Python 语法。
- Pattern A root layout 没有误迁到 `cloud/hfs/`。
- `README.md` metadata、`Dockerfile EXPOSE`、Nginx listen、healthcheck、smoke 端口一致。
- `hfs/` 内部路径、admin 默认关闭、`DEERFLOW_REF` 发布 pin surface 存在。

## Shell

```bash
make shell
```

常用路径：

```text
/home/user/app/deer-flow
/home/user/app/hfs
/data/deer-flow
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
