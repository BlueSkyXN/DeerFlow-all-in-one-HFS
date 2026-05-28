---
title: DeerFlow-all-in-one-HFS
emoji: 🦌
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
suggested_hardware: cpu-upgrade
pinned: false
license: gpl-3.0
---

# DeerFlow-all-in-one-HFS

`DeerFlow-all-in-one-HFS` packages [ByteDance DeerFlow](https://github.com/bytedance/deer-flow) as a single-container Hugging Face Docker Space.

This repository root is the deployable Hugging Face Space source.

```text
Hugging Face Docker Space
  └─ one container, one public port: 7860
      ├─ nginx reverse proxy       : 0.0.0.0:7860
      ├─ DeerFlow frontend / Next  : 127.0.0.1:3000
      ├─ DeerFlow gateway / FastAPI: 127.0.0.1:8001
      ├─ HFS ops service          : 127.0.0.1:8081
      └─ HFS admin service        : 127.0.0.1:8082
```

## Current target

- GitHub: [BlueSkyXN/DeerFlow-all-in-one-HFS](https://github.com/BlueSkyXN/DeerFlow-all-in-one-HFS)
- Hugging Face Space: [BlueSkyXN/DeerFlow-all-in-one-HFS](https://huggingface.co/spaces/BlueSkyXN/DeerFlow-all-in-one-HFS)
- App URL: <https://blueskyxn-deerflow-all-in-one-hfs.hf.space>

## Runtime profile

- Build-time clone from `bytedance/deer-flow`.
- Backend dependencies installed with `uv`.
- Frontend production build with `pnpm`.
- Runtime supervision by `supervisord`.
- External traffic goes through Nginx on port `7860`.
- Runtime data writes to `/data/deer-flow`.
- Default sandbox is `LocalSandboxProvider` with `allow_host_bash: false`.
- Docker/Kubernetes sandbox provisioning is disabled in this demo profile.

## Routes

| Path | Purpose |
|---|---|
| `/` | DeerFlow UI. |
| `/health` | DeerFlow Gateway health. |
| `/openapi.json` | Gateway OpenAPI schema. |
| `/api/v1/auth/setup-status` | Public first-boot auth setup status. |
| `/api/sandboxes` | Intentionally returns 404. |
| `/_ops/healthz` | Public HFS ops health. |
| `/_ops/readyz` | Public container readiness check. |
| `/_ops/status` | Token-protected supervisor/readiness status. |
| `/_ops/config` | Token-protected safe env and secret-presence view. |
| `/_admin/` | Browser admin control panel. |
| `/_admin/api/status` | Token-protected admin status. |

## Required configuration

Use Hugging Face Variables for non-sensitive values and Secrets for keys/tokens.

Recommended Variables:

```bash
DEER_FLOW_ENV=hf-space
DEER_FLOW_HOME=/data/deer-flow
DEER_FLOW_CONFIG_PATH=/data/deer-flow/config.yaml
DEER_FLOW_EXTENSIONS_CONFIG_PATH=/data/deer-flow/extensions_config.json
DEER_FLOW_SKILLS_PATH=/home/user/app/deer-flow/skills
GATEWAY_WORKERS=1
GATEWAY_ENABLE_DOCS=true
HF_HOME=/data/hf
DEER_FLOW_OPS_PORT=8081
DEER_FLOW_ADMIN_PORT=8082
DEER_FLOW_ADMIN_ENABLED=true
DEER_FLOW_ADMIN_ACTIONS_ENABLED=false
```

Recommended Secrets:

```bash
OPENROUTER_API_KEY=...
# or OPENAI_API_KEY=...
BETTER_AUTH_SECRET=...
DEER_FLOW_INTERNAL_AUTH_TOKEN=...
DEER_FLOW_OPS_TOKEN=...
DEER_FLOW_ADMIN_TOKEN=...
```

See [`docs/ENV_REFERENCE.md`](docs/ENV_REFERENCE.md) for the full env split.

## Local quick start

```bash
cp examples/local.env.example .env.local
# edit .env.local, at least OPENROUTER_API_KEY or OPENAI_API_KEY for chat flows
make build
make run
```

Smoke check:

```bash
make smoke
```

## Deploy

```bash
git push origin main
git remote add hf https://huggingface.co/spaces/BlueSkyXN/DeerFlow-all-in-one-HFS 2>/dev/null || true
git push hf main
```

Then watch the Space logs and verify:

```bash
curl -fsS https://blueskyxn-deerflow-all-in-one-hfs.hf.space/_ops/readyz
curl -fsS https://blueskyxn-deerflow-all-in-one-hfs.hf.space/health
curl -fsS https://blueskyxn-deerflow-all-in-one-hfs.hf.space/api/v1/auth/setup-status
```

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/DEPLOY_HF_SPACE.md`](docs/DEPLOY_HF_SPACE.md)
- [`docs/ENV_REFERENCE.md`](docs/ENV_REFERENCE.md)
- [`docs/LOCAL_TEST.md`](docs/LOCAL_TEST.md)
- [`docs/SECURITY.md`](docs/SECURITY.md)
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)

## License

This repository keeps the existing root license file. DeerFlow itself follows the license declared by [bytedance/deer-flow](https://github.com/bytedance/deer-flow).
