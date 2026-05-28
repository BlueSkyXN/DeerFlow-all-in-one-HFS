# Architecture

## Goal

Run DeerFlow inside a Hugging Face Docker Space as a single container with one public port.

This project intentionally keeps the App layer and removes the container-orchestrated sandbox layer from the first version.

## Process model

```text
container
├─ supervisord
│  ├─ gateway
│  │  └─ uvicorn app.gateway.app:app --host 127.0.0.1 --port 8001
│  ├─ frontend
│  │  └─ next start, Next.js on 127.0.0.1:3000
│  ├─ ops
│  │  └─ hfs/ops_service.py on 127.0.0.1:8081
│  ├─ admin
│  │  └─ hfs/admin_service.py on 127.0.0.1:8082
│  └─ nginx
│     └─ public listener on 0.0.0.0:7860
└─ /data/deer-flow
   ├─ config.yaml
   ├─ extensions_config.json
   ├─ threads/
   ├─ uploads/
   ├─ logs/
   └─ generated secrets, when not provided by HF Secrets
```

## Routing

| Public path | Internal target | Notes |
|---|---|---|
| `/` | `frontend:3000` | Next.js UI. |
| `/api/*` | `gateway:8001` | DeerFlow Gateway API. Auth middleware protects non-public routes. |
| `/api/langgraph/*` | `gateway:8001` | Rewritten to `/api/*`, matching DeerFlow's Nginx pattern. |
| `/docs` | `gateway:8001` | Swagger UI, if enabled. |
| `/redoc` | `gateway:8001` | ReDoc, if enabled. |
| `/openapi.json` | `gateway:8001` | OpenAPI schema, if enabled. |
| `/health` | `gateway:8001` | Public Gateway health check. |
| `/api/sandboxes` | disabled | Provisioner route intentionally returns 404. |
| `/_ops/healthz` | `ops:8081` | Public lightweight ops health. |
| `/_ops/readyz` | `ops:8081` | Public container readiness check. |
| `/_ops/status` | `ops:8081` | Token-protected supervisor/readiness status. |
| `/_ops/config` | `ops:8081` | Token-protected safe env and secret-presence view. |
| `/_admin/` | `admin:8082` | Token-driven browser control panel. |
| `/_admin/api/*` | `admin:8082` | Token-protected admin APIs; write actions are disabled unless explicitly enabled. |

## Why Nginx

Hugging Face Docker Spaces expose one configured public app port. The container may run multiple internal ports, but external users only get the configured public app port. Nginx keeps the frontend and backend same-origin and preserves streaming/SSE behavior for long-running agent requests.

The HF runtime uses `next build` during Docker image build and `next start` at runtime. A previous v0 shortcut used the upstream dev server, but HF proxying made the setup page remain at `Loading...` because the browser did not complete React hydration reliably while the dev HMR WebSocket failed. Production mode removes the HMR dependency and is the required runtime strategy for the public Space.

## Why supervisor

The container has five long-running processes. A minimal process supervisor gives:

- deterministic startup;
- autorestart for gateway/frontend/ops/admin/nginx;
- log aggregation to stdout/stderr;
- fixed `supervisorctl` status and restart hooks for token-protected admin actions.

## Ops and admin boundary

The ops surface is read-only. `/_ops/healthz` and `/_ops/readyz` are public so Docker/HF probes can use them. Detailed status and config require `DEER_FLOW_OPS_TOKEN`.

The admin surface is disabled unless `DEER_FLOW_ADMIN_ENABLED=true` and `DEER_FLOW_ADMIN_TOKEN` is configured. Fixed write actions such as `reload-nginx` and supervisor restart are additionally gated by `DEER_FLOW_ADMIN_ACTIONS_ENABLED=true`. There is no web terminal, SSH, tunnel, dynamic command runner, or user-supplied shell command surface.

## Sandbox profile

This project uses:

```yaml
sandbox:
  use: deerflow.sandbox.local:LocalSandboxProvider
  allow_host_bash: false
```

The choice is deliberate:

- Hugging Face Spaces should not be assumed to provide a Docker socket.
- Docker-in-Docker is outside this project's target scope.
- Kubernetes provisioner requires an external Kubernetes control plane and network design.
- Local sandbox with host bash disabled is acceptable for a constrained demo profile.

## Data layout

Runtime data defaults to:

```text
/data/deer-flow
```

This path is suitable for an attached Hugging Face Storage Bucket. Without a persistent bucket, Space restarts can lose runtime data.

## Build strategy

The Dockerfile does not vendor DeerFlow. It fetches upstream source at build time:

```dockerfile
ARG DEERFLOW_REPO=https://github.com/bytedance/deer-flow.git
ARG DEERFLOW_REF=main
```

For a reproducible deployment, pin `DEERFLOW_REF` to a commit SHA.

## Upgrade strategy

Recommended order:

1. Pin a working DeerFlow commit SHA.
2. Build and smoke-test locally or in a private Space.
3. Push to GitHub and Hugging Face Space.
4. Validate `/health`, `/_ops/readyz`, `/openapi.json`, UI load, setup status, and one simple authenticated chat when a model key is configured.
5. Only then update the Space public/protected visibility.
