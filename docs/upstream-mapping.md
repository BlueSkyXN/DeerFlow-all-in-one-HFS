# Mapping Official DeerFlow Deployment Modes to HFS

本仓库不是 DeerFlow 官方部署方式的替代品，而是把 DeerFlow app layer 包装成 Hugging Face Docker Space demo。核心适配点是：单容器、单公网端口、外部模型 API、禁用复杂 sandbox/provisioner。

## 当前上游基线

本仓当前验证目标是 `bytedance/deer-flow` commit `45865e9f3f5ac1cd05bfce9406b30ea8da864c52`，其 backend/frontend package version 为 `2.1.0`。这是审计时最新 `main` 的 source candidate，不是正式 `v2.1.0` release。Dockerfile 通过 shallow `git fetch --depth 1 <sha>` 获取该提交，避免把 SHA 当 branch clone 后退化成完整仓库下载。

从此前 live 镜像的 `8decfd327ea7bcef2d60598e8b8428b63908acc5` 到当前基线，上游构建和启动主契约仍保持 Python 3.12、Node 22、pnpm 10.26.2、`uv sync`、Gateway `8001`、frontend `3000`。HFS 必须跟进的是 `config_version: 26`、统一 SQLite 路径和 `AUTH_JWT_SECRET`；不是重新引入 provisioner 或改动公网端口。

## 官方本地开发形态

官方概念形态：

```text
native processes
├─ gateway  : 8001
├─ frontend : 3000
└─ nginx    : 2026 or configured ingress
```

HFS 适配：

```text
single Docker Space container
├─ gateway  : 127.0.0.1:8001
├─ frontend : 127.0.0.1:3000
├─ ops      : 127.0.0.1:8081
├─ admin    : 127.0.0.1:8082
└─ nginx    : 0.0.0.0:7860
```

这是一种 app-layer 合并部署，不是完整生产分布式部署。

## 官方 Docker Compose / production app layer

官方服务拆分通常包含：

```text
nginx
frontend
gateway
optional provisioner / sandbox services
```

HFS 中的变化：

- nginx、frontend、gateway、ops、admin 合并进一个容器。
- Docker Compose service DNS 改为 `127.0.0.1` upstream。
- 只暴露 HF 要求的单一公网端口 `7860`。
- 保留路径路由和 same-origin API 访问。
- 禁用 `/api/sandboxes` provisioner。
- SQLite 显式放到 `$DEER_FLOW_DB_DIR`，默认 `/data/deer-flow/data`，而不是 Gateway source checkout 下的相对目录。

## 官方 LocalSandboxProvider

HFS 保留最保守的 LocalSandboxProvider：

```yaml
sandbox:
  use: deerflow.sandbox.local:LocalSandboxProvider
  allow_host_bash: false
```

原因：

- HF Space 不应假设存在 Docker socket。
- 公共 demo 不应开放 host bash。
- v0 重点是 UI、auth、模型调用和基础研究流程，而不是执行任意代码。

## 官方 Docker / AIO sandbox

官方或社区 AIO sandbox 通常需要 Docker/Apple Container/Docker socket 一类能力。

HFS v0 不包含它，原因：

- Docker-in-Docker 不适合简单 HF Space demo。
- Docker-outside-of-Docker 需要 Docker socket，安全边界不适合公网 Space。
- 需要额外的配额、清理、审计和隔离策略。

如果后续需要，应改成外部 sandbox control plane：

```text
HFS Space
└─ UI + Gateway + Auth
   └─ HTTPS authenticated calls
      └─ External Sandbox Service
         ├─ Kubernetes / VM pool
         ├─ per-thread workspace
         ├─ quota and cleanup
         └─ audit logs
```

## 官方 Kubernetes provisioner

官方 production-like sandbox provisioner 更适合部署在你可控的 Kubernetes/VM 环境，不适合直接塞进单个 HF Space。

HFS v0 明确：

- `/api/sandboxes` 返回 404。
- 不运行 provisioner。
- 不创建 Pod。
- 不暴露 sandbox lifecycle API。

## 当前 HFS roadmap

### Phase 1: 可用 demo

- 单容器。
- Next production frontend。
- Gateway auth/setup 可用。
- Cloudflare AI Gateway 模型可用。
- ops/admin 诊断面可用。
- LocalSandboxProvider + host bash disabled。

### Phase 2: 私有强化 Space

- Private/Protected visibility。
- 更强管理员密码。
- 稳定 HF Secrets。
- provider-side budget limit。
- 限制上传、工具和 token。

### Phase 3: 外部 sandbox

- HFS 保持 UI/Gateway。
- 代码执行移到外部隔离服务。
- 增加 auth、quota、cleanup、audit。

### Phase 4: 生产部署

生产环境应优先使用官方 DeerFlow 部署方式，在自有基础设施上控制：

- TLS/ingress。
- auth/session。
- persistent database/storage。
- Docker/Kubernetes sandbox。
- request rate limit。
- audit logs。
- backup/restore。
