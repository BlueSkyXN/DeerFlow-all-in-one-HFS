# Security Notes

## Intended use

This project is for a DeerFlow-all-in-one-HFS demo or proof of concept. It is not a production multi-tenant deployment.

## Default security posture

The default config intentionally does the following:

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

It does not enable:

- `bash` tool;
- `file:write` tool group;
- Docker sandbox;
- Kubernetes provisioner;
- `/api/sandboxes` route;
- web terminal, SSH, tunnel, or arbitrary command execution surfaces.

## Ops and admin routes

Public routes:

```text
/_ops/healthz
/_ops/readyz
/_admin/
```

Token-protected routes:

```text
/_ops/status
/_ops/config
/_admin/api/status
/_admin/api/config
/_admin/api/reload-nginx
/_admin/api/restart
```

Use Hugging Face Secrets for:

```bash
DEER_FLOW_OPS_TOKEN
DEER_FLOW_ADMIN_TOKEN
```

`/_admin/api/reload-nginx` and `/_admin/api/restart` are fixed actions only. They are unavailable unless all of these are true:

```bash
DEER_FLOW_ADMIN_ENABLED=true
DEER_FLOW_ADMIN_TOKEN=<strong-token>
DEER_FLOW_ADMIN_ACTIONS_ENABLED=true
```

Keep `DEER_FLOW_ADMIN_ACTIONS_ENABLED=false` for normal demo operation.

## Why host bash is disabled

`LocalSandboxProvider` runs within the same application environment. It is useful for a constrained demo, but it is not a strong isolation boundary. Enabling host bash in a public Space can expose the container, secrets, filesystem, and network egress to user-driven agent behavior.

## Upload conversion

`auto_convert_documents` is disabled because parsing Office/PDF files on the backend host increases attack surface. Enable it only for trusted users and after reviewing parser dependencies and resource impact.

## Model cost exposure

A public Space with an API key can become a cost sink. Use at least one of:

- Private/Protected Space visibility;
- provider-side spending limits;
- short request timeouts;
- low max tokens;
- rate limiting in an external reverse proxy;
- separate low-limit API keys for demo use.

## Secrets

Use Hugging Face Secrets for:

```bash
OPENROUTER_API_KEY
OPENAI_API_KEY
BETTER_AUTH_SECRET
DEER_FLOW_INTERNAL_AUTH_TOKEN
DEER_FLOW_OPS_TOKEN
DEER_FLOW_ADMIN_TOKEN
TAVILY_API_KEY
SERPER_API_KEY
JINA_API_KEY
```

Do not store secrets in `hfs/config.hfs.yaml`, `.env`, README, docs, PR text, or committed test snapshots.

## Public Space checklist

Before making the Space public:

- Confirm `/api/sandboxes` returns 404.
- Confirm `bash` is not present in `/data/deer-flow/config.yaml` tools.
- Confirm `file:write` is not enabled unless paths are constrained.
- Confirm `allow_host_bash: false`.
- Confirm `auto_convert_documents: false`, unless uploads are trusted.
- Confirm model API keys have budget limits.
- Confirm logs do not print secrets.
- Confirm generated auth secrets are stable via persistent `/data`, or provide them as HF Secrets.
- Confirm `DEER_FLOW_ADMIN_ACTIONS_ENABLED=false` unless a short maintenance window requires it.

## Production route

For production, prefer official DeerFlow deployment on infrastructure where you control:

- Docker or Kubernetes sandbox isolation;
- persistent storage and backups;
- authentication;
- TLS and ingress;
- rate limiting;
- audit logs;
- per-user resource quotas.

A better production split is:

```text
HFS / public demo UI, optional
  -> external authenticated DeerFlow deployment
      -> isolated Docker/Kubernetes sandbox control plane
```
