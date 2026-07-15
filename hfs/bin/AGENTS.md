# hfs/bin navigation card

`hfs/bin/` contains the runtime entrypoint and Docker healthcheck scripts.
Read this after `hfs/AGENTS.md` before modifying startup, managed config, generated secrets, persistence probes, or health checks.
Key files: `entrypoint.sh`, `healthcheck.sh`.

## Local invariants

- Scripts are `bash` with `set -Eeuo pipefail`.
- `entrypoint.sh` resolves writable `DEER_FLOW_HOME`, preferring `/data/deer-flow` and falling back to `/tmp/deer-flow` only when `/data` is not writable.
- `DEER_FLOW_MANAGED_CONFIG=true` copies `/home/user/app/hfs/config/config.hfs.yaml` to `$DEER_FLOW_CONFIG_PATH` on every startup; `false` only creates the target config when absent.
- `DEER_FLOW_DB_DIR` resolves under the final writable `$DEER_FLOW_HOME`; managed config points SQLite there.
- `AUTH_JWT_SECRET` and `DEER_FLOW_INTERNAL_AUTH_TOKEN` may be generated under `$DEER_FLOW_HOME`; `BETTER_AUTH_SECRET` is accepted only as legacy JWT migration input.
- `healthcheck.sh` must check `http://127.0.0.1:7860/_ops/readyz` through Nginx, not the internal gateway or ops port directly.

## Local rules

- Keep startup logs useful but never print raw secret values or `.env.local` contents.
- Env default changes must be reflected in `Dockerfile`, `examples/*.env`, `docs/configuration.md`, `docs/deployment.md`, `docs/development.md`, and `README.md` when applicable.
- Changes to config copy paths must stay aligned with `Dockerfile COPY`, `hfs/config/`, and `hfs/supervisor/supervisord.conf`.

## Do not

- Do not make startup depend on interactive input, sudo, Docker socket access, or external network calls at runtime.
- Do not remove the persistence probe without updating ops readiness and `scripts/static-check.sh`.
- Do not make generated secrets world-readable or commit generated secret files.

## Validation

- `bash -n hfs/bin/entrypoint.sh hfs/bin/healthcheck.sh` checks shell syntax.
- `make static-check` is the default no-Docker validation.
- For startup behavior changes, run `make build`, `make run`, then `make smoke` when Docker, network, and `.env.local` are available.
