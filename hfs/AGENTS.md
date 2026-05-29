# hfs navigation card

`hfs/` is the runtime guardrail layer copied into the image at `/home/user/app/hfs`.
Read this before changing runtime scripts, Nginx, Supervisor, config, healthcheck, ops, or admin files.
They control routes, startup order, generated secrets, default tools, and ops/admin surfaces.

## Layout

| Path | Responsibility |
|---|---|
| `bin/` | `entrypoint.sh` and `healthcheck.sh`. |
| `config/` | Managed DeerFlow config and extensions config copied into runtime data. |
| `nginx/` | Public reverse proxy on port `7860`. |
| `supervisor/` | Process orchestration for Gateway, frontend, ops, admin, and Nginx. |
| `services/` | Python stdlib ops/admin services. |

## High-risk boundaries

- Nginx is the only public listener on port `7860`; route mistakes can expose internals or break the Space.
- Supervisor starts Gateway, frontend, ops, admin, and Nginx; process command changes affect readiness and app usability.
- With `DEER_FLOW_MANAGED_CONFIG=true`, `bin/entrypoint.sh` overwrites `$DEER_FLOW_CONFIG_PATH` from `config/config.hfs.yaml` on every startup.
- `/_ops/*` and `/_admin/*` are public routes through Nginx; token checks and redaction are security boundaries.
- `config/config.hfs.yaml` controls models, tools, uploads, sandbox, loop detection, and token usage.

## Required before changes

- Check root `AGENTS.md` first for cross-file update requirements.
- Route, port, or health changes: inspect `nginx/nginx.conf`, `bin/healthcheck.sh`, `supervisor/supervisord.conf`, and `../scripts/smoke-test.sh`.
- Env changes: inspect `bin/entrypoint.sh`, `../Dockerfile`, `services/*.py` when relevant, `../examples/*.env`, env docs, and `../README.md`.
- Config or ops/admin changes: verify public-demo posture, token handling, and response redaction.

## Do not

- Do not enable host bash, unrestricted `file:write`, Docker sandbox, Kubernetes provisioner, or document auto-conversion without explicit user approval.
- Do not change `/api/sandboxes` from intentional `404` unless adding a safe remote sandbox/provisioner design.
- Do not expose raw secrets, token values, `.env.local` contents, private URLs, or persistent config contents.
- Do not assume `/data` is persistent; generated secrets are stable only when `$DEER_FLOW_HOME` persists.

## Validation

Use root validation guidance. For runtime changes, preferred full check is `make build`, `make run`, then `make smoke` when Docker, network, and env values are available.
