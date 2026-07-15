# hfs navigation card

`hfs/` is the runtime guardrail layer copied into the image at `/home/user/app/hfs`.
Read this before changing runtime scripts, Nginx, Supervisor, config, healthcheck, ops, or admin files.
Then read the nested card for the exact subdirectory.

## Local map

Nested cards exist for `bin/`, `config/`, `nginx/`, `supervisor/`, and `services/`. Read the matching nested card before editing files in that subdirectory.

## Cross-cutting invariants

- Nginx is the only public listener on port `7860`.
- Gateway, frontend, ops, and admin remain internal on `127.0.0.1` ports `8001`, `3000`, `8081`, and `8082`.
- With `DEER_FLOW_MANAGED_CONFIG=true`, `bin/entrypoint.sh` overwrites `$DEER_FLOW_CONFIG_PATH` from `config/config.hfs.yaml` on every startup.
- SQLite stays under the resolved `$DEER_FLOW_DB_DIR`, which defaults below the final writable `$DEER_FLOW_HOME`.
- `/_ops/*` and `/_admin/*` are public routes; token checks, redaction, body/method limits, and security headers are boundaries.
- `config/config.hfs.yaml` is runtime behavior, not just sample config.

## Required before changes

- Route, port, or health changes: inspect Nginx, healthcheck, Supervisor, and `../scripts/smoke-test.sh`.
- Env changes: inspect `bin/entrypoint.sh`, `../Dockerfile`, relevant `services/*.py`, `../examples/*.env`, env docs, and `../README.md`.
- Config or ops/admin changes: verify demo posture, token handling, and redaction.

## Do not

- Do not enable host bash, unrestricted `file:write`, Docker sandbox, Kubernetes provisioner, or document auto-conversion without explicit user approval.
- Do not change `/api/sandboxes` from intentional `404` unless adding a safe remote sandbox/provisioner design.
- Do not expose raw secrets, token values, `.env.local`, private URLs, or persistent config contents.
- Do not assume `/data` is persistent; generated secrets are stable only when `$DEER_FLOW_HOME` persists.

## Validation

Use root validation guidance. For HFS changes, start with `make static-check`. Runtime behavior changes need `make build`, `make run`, then `make smoke` when Docker, network, and env values are available.
