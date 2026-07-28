# DeerFlow-all-in-one-HFS repository agent instructions

## Purpose

本仓库是 `DeerFlow-all-in-one-HFS` 的 Hugging Face Docker Space 包装仓。仓库根目录就是 Space 部署源；Docker 构建期通过 `DEERFLOW_REPO` / `DEERFLOW_REF` 拉取上游 `bytedance/deer-flow`，再用本仓的 HFS runtime 层封装成 single-container demo/PoC。

## Codex startup behavior

- Codex 通常从仓库根目录启动；本文件是启动期主规则和目录 router。
- 子目录 `AGENTS.md` 是按需 navigation card。修改带有本地 `AGENTS.md` 的目录前，必须先读取对应卡片。
- 如果目标路径有多层本地卡片，按从浅到深读取。例如修改 `hfs/nginx/nginx.conf` 前，先读 `hfs/AGENTS.md`，再读 `hfs/nginx/AGENTS.md`。
- 如果从子目录启动，Codex 也可能自动加载路径链上的本地 `AGENTS.md`；仍以本文件的目录地图理解根启动 workflow。
- 不要把用户级全局偏好复制进本仓库文件；本文件只记录本仓库的工程边界、命令和安全不变量。
- 本仓库文档、脚本、Docker/HFS 配置里不要写入真实 token、账号、私有 URL、`.env.local` 内容、HF Secrets 或本机私有路径。

## Directory map

| Path | Responsibility | Local AGENTS.md | Read when |
|---|---|---:|---|
| `Dockerfile` | Hugging Face Docker Space 镜像定义；安装 Python 3.12、Node.js 22、pnpm、nginx、supervisor、tini、`uv`，并构建上游 DeerFlow backend/frontend | No | 修改构建参数、系统依赖、上游 clone/ref、frontend/backend build 流程、COPY 路径或镜像入口前 |
| `Makefile` | 本地 Docker build/run/smoke/shell/clean 命令面 | No | 修改本地运行流程、端口、数据目录、image tag、env 文件或 smoke target 前 |
| `hfs-dev.toml` | HFS v2 项目语义与环境变量键名登记；build pin 仍以 Dockerfile/Makefile 为准 | No | 修改 HFS v2 语义、环境变量分类或 checker 期望前 |
| `.github/workflows/` | GitHub Actions；当前只运行 static-check | No | 修改 CI 触发条件、runner、check 命令或 required gate 前 |
| `hfs/` | Runtime guardrail layer，复制到镜像内 `/home/user/app/hfs` | Yes | 修改任何 runtime script、config、Nginx、Supervisor、ops/admin service 前 |
| `hfs/bin/` | Runtime shell 入口和 Docker healthcheck | Yes | 修改启动流程、runtime home、managed config、secret 生成、persistence probe 或 health endpoint 前 |
| `hfs/config/` | HFS 默认 DeerFlow config 和 extensions config | Yes | 修改默认模型、tools、sandbox、uploads、loop detection、MCP/extensions 或 managed config 行为前 |
| `hfs/nginx/` | Nginx public route proxy 和 same-origin 入口 | Yes | 修改公开路由、端口、header/WebSocket 透传、body limit、method limit 或 `/api/sandboxes` 行为前 |
| `hfs/supervisor/` | Supervisor 进程编排 | Yes | 修改 Gateway/frontend/ops/admin/nginx 启动命令、端口、顺序、重启策略或日志行为前 |
| `hfs/services/` | HFS ops/admin Python stdlib services | Yes | 修改 public control surface、token 校验、redaction、admin action、audit log 或 security headers 前 |
| `docs/` | 面向使用者的部署、架构、本地测试、安全和排障文档 | No | 修改文档时对照实际 `Dockerfile`、`Makefile`、`hfs/`、`examples/` 和 `scripts/`，不要只改文案 |
| `examples/` | Hugging Face Variables/Secrets 和本地 `.env.local` 模板 | No | 修改 env 变量名、默认值、secret 分类或部署文档里的配置清单前 |
| `scripts/` | 本地辅助脚本；当前包含 static check 和 smoke test | No | 修改 smoke endpoint、HTTP 期望值、token header、static contract 或 Makefile target 前 |
| `local/` | 本机参考材料和历史/快速开发记录；被 Git 和 Docker ignore，不是当前 Space 部署源 | No | 只在用户明确要求整理本机参考材料或同步历史记录时修改 |
| repository root | Hugging Face Space metadata、README、license、ignore 文件、Codex router 和外层 GitHub/HF 仓库边界 | No | 修改 Space metadata、部署源定位、仓库级指令、release note 或 Git/HF 发布说明前 |

## On-demand cat protocol

Before editing files under a directory that has a local `AGENTS.md`, read that file first:

```bash
cat hfs/AGENTS.md
cat hfs/<subdir>/AGENTS.md
```

Read nested cards from shallow to deep. For example:

- `hfs/bin/entrypoint.sh`: read `hfs/AGENTS.md`, then `hfs/bin/AGENTS.md`.
- `hfs/config/config.hfs.yaml`: read `hfs/AGENTS.md`, then `hfs/config/AGENTS.md`.
- `hfs/services/admin_service.py`: read `hfs/AGENTS.md`, then `hfs/services/AGENTS.md`.

If a future target directory contains `AGENTS.override.md`, stop and ask the user how to handle the override strategy before writing a same-directory `AGENTS.md`.

## Project shape

- The repository root is the Hugging Face Docker Space source. Run Makefile commands from the repository root, not from `local/`.
- `local/` is not part of the current cloud build path. Do not copy rules from old `local/`-as-package-root instructions unless the current tree confirms that boundary has changed again.
- `Dockerfile` builds a Python 3.12 image, installs Node.js 22, pnpm, nginx, supervisor, tini and `uv`, then shallow-fetches the exact upstream DeerFlow `DEERFLOW_REF` commit.
- Backend dependencies are installed under `/home/user/app/deer-flow/backend` via `uv sync`; frontend dependencies and production assets are built under `/home/user/app/deer-flow/frontend` via `pnpm install --frozen-lockfile` and `pnpm exec next build --webpack`.
- Runtime exposes one public port, `7860`, through Nginx. Internal services are DeerFlow Gateway on `127.0.0.1:8001`, Next.js frontend on `127.0.0.1:3000`, ops service on `127.0.0.1:8081`, and admin service on `127.0.0.1:8082`.
- Runtime data defaults to `/data/deer-flow`, with SQLite under `/data/deer-flow/data`, falling back to `/tmp/deer-flow` when `/data` is not writable. `/data` is persistent only when Hugging Face Storage is attached.
- Default sandbox profile is `deerflow.sandbox.local:LocalSandboxProvider` with `allow_host_bash: false`.
- `hfs/nginx/nginx.conf` intentionally returns `404` for `/api/sandboxes`; do not re-enable provisioner routes as a casual fix.
- `/_ops/*` and `/_admin/*` are externally reachable through Nginx. Treat them as public control surfaces even when individual endpoints require tokens.

## Commands

Run these from the repository root unless otherwise stated.

| Command | Purpose | Scope | Sandbox notes |
|---|---|---|---|
| `make build` | Build the Docker image tagged by `IMAGE`, default `deerflow-all-in-one-hfs`; defaults to the committed upstream SHA and passes `DEERFLOW_REF` to Docker build | repo root | Requires Docker daemon, BuildKit-compatible build, and network access to GitHub, ghcr.io, Debian apt, PyPI/uv index and npm registry |
| `make run` | Run the built image on `PORT`, default `7860`, mounting `$(PWD)/.data` to `/data` and loading `.env.local` | repo root | Requires Docker daemon and `.env.local`; may use real model/search/admin tokens from local env file |
| `make smoke` | Run `./scripts/smoke-test.sh http://localhost:$(PORT)` | repo root | Requires a running container/service on the selected port and `curl`; checks `/health`, `/openapi.json`, `/api/v1/auth/setup-status`, `/api/sandboxes`, `/_ops/*`, and `/_admin/` |
| `make static-check` | Run no-Docker HFS contract, shell/Python syntax, and dependency-free ops/admin service integration checks | repo root | No Docker daemon or secrets required; requires `bash`, `python3`, and standard library `tomllib` |
| `make shell` | Open `/bin/bash` inside the image with `.env.local` and `.data` mounted | repo root | Requires Docker daemon and `.env.local`; interactive command |
| `make clean` | Delete root `.data` | repo root | Destructive for local runtime data; ask before running if user data may matter |
| `./scripts/smoke-test.sh http://localhost:7860` | Direct smoke script invocation | repo root | Requires running service; expected `/api/sandboxes` result is `404`, not `200`; optional `DEER_FLOW_OPS_TOKEN` / `DEER_FLOW_ADMIN_TOKEN` enable token-protected checks |

There are no repository-root package manager scripts, Python test commands, dedicated lint/typecheck targets, Docker Compose files, or zip/package target confirmed in the current checkout. Do not invent `npm`, `pnpm`, `pytest`, `ruff`, `uv run`, `docker compose`, or `make zip` commands unless you first verify they exist in the current tree.

## Global rules

- Keep changes minimal and scoped. This repository is a wrapper; avoid modifying upstream DeerFlow assumptions unless the wrapper files require it.
- Treat the repository root as the source of truth for the Hugging Face Space package. If a future task copies or syncs files to a separate Space repo, make clear whether it uses the root contents or an explicit staging directory.
- The committed `DEERFLOW_REF` default must be a verified commit SHA. `main` may be supplied only as an explicit local development override, not as a release default.
- Build-time mirror args (`APT_MIRROR`, `NPM_REGISTRY`, `UV_INDEX_URL`) are optional acceleration knobs. Do not hard-code local/private mirrors into committed files.
- Do not add long-lived dependencies unless they are necessary for this wrapper layer and cannot be handled by existing OS packages, `uv`, `pnpm`, Nginx, Supervisor, Python standard library, or shell.
- Preserve Hugging Face Docker Space constraints: one public app port, no Docker socket assumption, UID 1000 runtime, writable data under `/data` when available.
- Keep public endpoints same-origin through Nginx. Route or port changes must update `hfs/nginx/nginx.conf`, `hfs/bin/healthcheck.sh`, `scripts/smoke-test.sh`, `README.md`, and relevant docs together.
- If changing env variables, update all affected places together: `Dockerfile`, `hfs/bin/entrypoint.sh`, `hfs/services/*.py` when applicable, `examples/*.env`, `docs/configuration.md`, `docs/deployment.md`, `docs/development.md`, and `README.md`.
- If changing default config in `hfs/config/config.hfs.yaml`, check security posture in `docs/security.md`, env docs, and smoke expectations in `scripts/smoke-test.sh`.
- Keep secrets out of committed files. Env example files may use placeholders only.
- Shell scripts should remain `bash` with `set -Eeuo pipefail` unless there is a specific compatibility reason to change.
- Python runtime helper services in `hfs/` are public-HFS support code; avoid adding framework dependencies unless they are already installed in the Docker image or clearly justified.
- Do not run destructive, external, publishing, push, deploy, Space restart, hardware/visibility, or variable/secret mutation commands unless the user explicitly asks.

## Runtime invariants

- Public port remains `7860` unless the user explicitly asks to change the Hugging Face Space port and all docs/configs are updated.
- Gateway remains internal on `127.0.0.1:8001`; frontend remains internal on `127.0.0.1:3000`; ops remains internal on `127.0.0.1:8081`; admin remains internal on `127.0.0.1:8082`; Nginx is the public listener.
- Docker healthcheck uses `http://127.0.0.1:7860/_ops/readyz` through Nginx, not the internal gateway port directly.
- `/api/langgraph/*` is rewritten to `/api/*` for the Gateway.
- `/api/sandboxes` intentionally returns `404` because provisioner/Kubernetes sandbox management is disabled in this HFS demo profile.
- `DEER_FLOW_MANAGED_CONFIG=true` means startup copies `hfs/config/config.hfs.yaml` to `$DEER_FLOW_CONFIG_PATH` each time. If false, startup only creates an initial config when the target file is absent.
- `AUTH_JWT_SECRET` and `DEER_FLOW_INTERNAL_AUTH_TOKEN` may be generated into `$DEER_FLOW_HOME` if not provided. `BETTER_AUTH_SECRET` is legacy JWT migration input only. Generated values are stable only when `$DEER_FLOW_HOME` persists.
- Default tools are web plus file read-oriented tools. Do not enable `bash`, unrestricted `file:write`, Docker sandbox, Kubernetes provisioner, or document auto-conversion for public demos without explicit user decision and documentation updates.
- `DEER_FLOW_ADMIN_ENABLED` and `DEER_FLOW_ADMIN_ACTIONS_ENABLED` should remain false for public demo posture unless the user explicitly approves remote administrative APIs/actions and related documentation updates.
- Ops/admin status endpoints must not expose raw secrets. They may report presence, derived status, or redacted values only.

## Do not

- Do not commit `.env.local`, real Hugging Face Secrets, model API keys, generated auth secrets, private bucket URLs, private Space URLs, customer data, or local absolute paths.
- Do not print real `.env.local` values in chat, logs, docs, PR text, tests, snapshots, screenshots, or public examples.
- Do not enable host bash or write tools in `hfs/config/config.hfs.yaml` as a convenience fix.
- Do not change `/api/sandboxes` from the intentional `404` behavior unless the task is explicitly about adding a safe remote sandbox/provisioner design.
- Do not assume Docker-in-Docker or `/var/run/docker.sock` is available on Hugging Face Space.
- Do not move `Dockerfile`, `README.md`, `hfs/`, `examples/`, or `scripts/` out of the repository root without updating deployment instructions that expect root to be the Space source.
- Do not edit generated or upstream-cloned DeerFlow source inside the built image; persistent changes belong in this wrapper repo or an explicit upstream fork/ref.
- Do not run `make clean` if `.data` may contain user state unless the user has approved deletion.
- Do not push to GitHub or Hugging Face, restart a Space, change Space hardware/visibility, or update variables/secrets without explicit user approval.

## Validation

Choose the smallest validation that matches the change and state what was actually run.

| Change type | Suggested validation | Notes |
|---|---|---|
| AGENTS-only changes | Review affected `AGENTS.md` files and run `git diff -- AGENTS.md hfs/AGENTS.md hfs/*/AGENTS.md` | No build required; only `AGENTS.md` files should change |
| Documentation-only changes under `docs/` or `README.md` | Read the changed doc against the referenced runtime file(s) | No build required unless command examples changed materially |
| Env template changes | Compare `examples/*.env` with `Dockerfile`, `hfs/bin/entrypoint.sh`, `hfs/services/*.py` when applicable, `README.md`, and `docs/configuration.md` / `docs/deployment.md` | Do not print real `.env.local` values |
| HFS directory or contract changes | `make static-check` | No Docker required; checks Pattern A layout, SHA/config/persistence/security contracts, syntax, and local ops/admin endpoint behavior |
| Smoke endpoint changes | `make smoke` | Requires running container on `PORT`; `/api/sandboxes` should remain `404` unless intentionally changed |
| Runtime script/config changes under `hfs/` | Read `hfs/AGENTS.md` plus the relevant nested card, then run `make static-check`; run `make build`, `make run`, and `make smoke` when Docker/network/credentials are available | Full runtime check is network-heavy and may use real API keys |
| Dockerfile dependency/build changes | `make build` | Network-heavy; may be slow because it clones upstream DeerFlow and installs Python/Node dependencies |
| Public route or port changes | `make static-check`, `make build`, `make run`, `make smoke`, plus manual curl checks for changed routes | Must update Nginx, healthcheck, smoke, README, and docs together |
| CI changes | Inspect `.github/workflows/static-check.yml`, then run `make static-check` locally if possible | GitHub Actions currently runs `./scripts/static-check.sh` |

If validation is skipped, say so explicitly and explain whether it was skipped because the change is AGENTS-only, because it needs Docker/network/credentials, or because it would be destructive.

## Notes for future agents

- Hugging Face Space live state is time-sensitive. Check it live before making claims about runtime stage, hardware, app URL, repo SHA, endpoint health, or secrets/variables.
- Existing docs mention a demo/PoC scope, not production multi-tenant security. Preserve that boundary unless the user asks for production hardening.
- This repo is a wrapper around upstream DeerFlow. If upstream config schema, route names, frontend start behavior, or dependency commands change, update wrapper docs and smoke checks from observed runtime behavior rather than assumptions.
- The working tree may contain user edits. Do not revert unrelated changes while refreshing AGENTS.
