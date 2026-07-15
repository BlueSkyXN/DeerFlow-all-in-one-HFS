# hfs/supervisor navigation card

`hfs/supervisor/` defines runtime process orchestration for the single-container Space.
Read this after `hfs/AGENTS.md` before changing process commands, ports, priorities, restart behavior, or log routing.
Key file: `supervisord.conf`.

## Local invariants

- Gateway runs from `/home/user/app/deer-flow/backend` via `uv run --no-sync uvicorn app.gateway.app:app --host 127.0.0.1 --port 8001`.
- Frontend runs from `/home/user/app/deer-flow/frontend` via `pnpm start --hostname 127.0.0.1 --port 3000`; do not switch back to Next dev server.
- Ops and admin run with `/usr/local/bin/python` from `/home/user/app/hfs/services`.
- Nginx runs from `/home/user/app/hfs/nginx/nginx.conf` and is the only public listener.
- Process priorities keep Gateway/frontend before ops/admin and Nginx last enough for readiness to converge.
- `stopasgroup=true`, `killasgroup=true`, and stdout/stderr forwarding to container logs are part of operational behavior.

## Local rules

- Command or port changes must be synchronized with `Dockerfile`, `hfs/nginx/nginx.conf`, `hfs/bin/healthcheck.sh`, `scripts/smoke-test.sh`, README, and docs.
- Keep `GATEWAY_WORKERS` configurable; CPU Space defaults should remain conservative.
- Use absolute runtime paths that exist inside the image.

## Do not

- Do not add a new long-running process without documenting its port, readiness impact, logs, and Space resource cost.
- Do not make Supervisor invoke commands that require interactive input, sudo, Docker, or external secrets beyond environment variables.
- Do not hide process logs in files that are not visible in container stdout/stderr unless there is a separate runbook update.

## Validation

- `make static-check` verifies expected moved service/config paths.
- Process command changes usually require `make build`, `make run`, then `make smoke` when Docker, network, and env values are available.
- If only syntax-free comments changed, explain that no runtime validation was needed.
