# Local Test

## Prerequisites

- Docker with BuildKit.
- Network access to GitHub, PyPI, npm registry, and ghcr.io.
- A model API key, such as OpenRouter or OpenAI, if you want to run chat flows.

## Prepare env file

```bash
cp examples/local.env.example .env.local
```

Edit `.env.local`:

```bash
OPENROUTER_API_KEY=sk-or-...
# or
OPENAI_API_KEY=sk-...
```


## Build from repository root

```bash
make build
```

Equivalent manual command:

```bash
docker build \
  --build-arg DEERFLOW_REF=main \
  -t deerflow-all-in-one-hfs .
```

For reproducibility:

```bash
docker build \
  --build-arg DEERFLOW_REF=<commit-sha> \
  -t deerflow-all-in-one-hfs:<commit-sha> .
```

## Run

```bash
make run
```

Equivalent manual command:

```bash
mkdir -p .data
docker run --rm -it \
  -p 7860:7860 \
  --env-file .env.local \
  -v "$PWD/.data:/data" \
  deerflow-all-in-one-hfs
```

## Smoke test

```bash
make smoke
```

Expected checks:

- `/health` returns HTTP 200.
- `/openapi.json` returns HTTP 200.
- `/api/v1/auth/setup-status` returns HTTP 200.
- `/api/sandboxes` returns HTTP 404 because provisioner is disabled.
- `/_ops/healthz` and `/_ops/readyz` return HTTP 200.
- `/_admin/` returns HTTP 200.
- `/_ops/status` is checked when `DEER_FLOW_OPS_TOKEN` is present in the shell.
- `/_admin/api/status` is checked when `DEER_FLOW_ADMIN_TOKEN` is present in the shell.

## Shell into image

```bash
make shell
```

Useful paths:

```text
/home/user/app/deer-flow
/home/user/app/hfs
/data/deer-flow
```

## Local persistent data

`make run` mounts:

```text
./.data -> /data
```

Remove local runtime state:

```bash
make clean
```

## Common local overrides

Use a faster npm mirror:

```bash
docker build \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
  -t deerflow-all-in-one-hfs .
```

Use a PyPI mirror:

```bash
docker build \
  --build-arg UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  -t deerflow-all-in-one-hfs .
```

Use an apt mirror:

```bash
docker build \
  --build-arg APT_MIRROR=mirrors.aliyun.com \
  -t deerflow-all-in-one-hfs .
```
