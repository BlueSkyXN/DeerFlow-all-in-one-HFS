# hfs/nginx navigation card

`hfs/nginx/` contains the public reverse proxy for the Hugging Face Space.
Read this after `hfs/AGENTS.md` before changing routes, ports, headers, body limits, method limits, or WebSocket behavior.
Key file: `nginx.conf`.

## Local invariants

- Nginx listens on public port `7860`; all other services remain internal on `127.0.0.1`.
- Upstreams are `deerflow_gateway` on `8001`, `deerflow_frontend` on `3000`, `deerflow_ops` on `8081`, and `deerflow_admin` on `8082`.
- `/_ops/` allows GET only with a small body limit and proxies to ops.
- `/_admin/` allows GET/POST only with a small body limit and proxies to admin.
- `/api/langgraph/*` rewrites to `/api/*` for the Gateway.
- `/api/sandboxes` intentionally returns `404` because sandbox provisioner management is disabled in this demo profile.
- Upload routes have an explicit larger body limit; the default body limit should stay small.
- Access logs must omit query strings, and control-surface redirects must not preserve query parameters that could contain credentials.

## Local rules

- Route or port changes must stay aligned with `hfs/bin/healthcheck.sh`, `hfs/supervisor/supervisord.conf`, `scripts/smoke-test.sh`, `README.md`, and docs.
- Preserve forwarded host/proto headers and frontend WebSocket upgrade headers unless the observed runtime proves a different contract.
- Treat ops/admin route changes as public security surface changes.

## Do not

- Do not expose Gateway, frontend, ops, or admin on a public port other than Nginx.
- Do not turn `/api/sandboxes` into a live provisioner route without an explicit safe design.
- Do not remove method limits, small body limits, or no-cache proxy behavior from control routes without a documented reason.

## Validation

- `make static-check` validates key Nginx route/port/body-limit invariants without Docker.
- `make smoke` validates public route expectations when a container/service is running.
- Public route changes should get `make build`, `make run`, `make smoke`, plus targeted `curl` checks for the changed route when Docker/network are available.
