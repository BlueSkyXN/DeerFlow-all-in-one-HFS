# Troubleshooting

## Space stuck at starting

Check:

- `README.md` has `sdk: docker`.
- `README.md` has `app_port: 7860`.
- `Dockerfile` exists at repository root for Hugging Face builds.
- Nginx listens on `0.0.0.0:7860`.
- `/_ops/healthz` returns 200 through Nginx.
- `/health` returns 200 through Nginx.
- Logs show supervisor programs started: gateway, frontend, ops, admin, nginx.

## `/_ops/readyz` fails

`/_ops/readyz` checks gateway, frontend, ops port, writable data directory, config file and extensions config file.

Common causes:

- gateway failed to load `/data/deer-flow/config.yaml`;
- frontend did not start after `pnpm start`;
- `/data` is not writable;
- first boot is still warming up.

Use token-protected status when configured:

```bash
curl -H "Authorization: Bearer $DEER_FLOW_OPS_TOKEN" \
  https://blueskyxn-deerflow-all-in-one-hfs.hf.space/_ops/status
```

## `/health` fails

Check gateway logs. Most common causes:

- backend dependency install failed during build;
- config schema changed upstream;
- `/data/deer-flow/config.yaml` contains invalid YAML;
- generated config references a model provider without a required dependency;
- `uv run --no-sync` cannot find the prebuilt `.venv`.

To isolate locally:

```bash
make shell
cd /home/user/app/deer-flow/backend
PYTHONPATH=. uv run --no-sync uvicorn app.gateway.app:app --host 127.0.0.1 --port 8001
```

## UI loads but chat fails

Check:

- fresh DeerFlow instances require first admin setup via `/setup` or the UI setup flow;
- `OPENROUTER_API_KEY` or `OPENAI_API_KEY` is configured;
- selected model name exists in `/data/deer-flow/config.yaml`;
- provider base URL and model name are valid;
- provider quota or billing is active.

Note: upstream DeerFlow auth middleware protects non-public API routes, so unauthenticated `/api/models` can return 401. This is expected after the auth hardening upstream.

## `/api/models` returns 401

This is expected for unauthenticated requests. Use these public endpoints for smoke checks instead:

```text
/health
/openapi.json
/api/v1/auth/setup-status
/_ops/healthz
/_ops/readyz
```

After login/setup, the browser UI can call authenticated API routes with the session cookie.

## `/api/models` empty or errors after login

Open `/data/deer-flow/config.yaml` and verify:

```yaml
models:
  - name: ...
    use: langchain_openai:ChatOpenAI
    model: ...
    api_key: $OPENROUTER_API_KEY
```

Make sure the referenced environment variable exists in HF Secrets.

## Build fails while fetching DeerFlow

Possible causes:

- GitHub outage/rate limit;
- wrong `DEERFLOW_REF`;
- private fork without build-time credentials.

Use a stable tag/commit SHA when possible.

## Build fails during `pnpm install`

Try setting:

```bash
NPM_REGISTRY=https://registry.npmmirror.com
```

as a build arg or Space build Variable.

## Build fails during `uv sync`

Try setting:

```bash
UV_INDEX_URL=https://pypi.org/simple
```

or a regional mirror. If DeerFlow added optional native dependencies, you may need extra build packages in the Dockerfile.

## `/_admin/api/*` returns 403

Check Variables/Secrets:

```bash
DEER_FLOW_ADMIN_ENABLED=true
DEER_FLOW_ADMIN_TOKEN=<secret>
```

Fixed write actions also require:

```bash
DEER_FLOW_ADMIN_ACTIONS_ENABLED=true
```

Keep write actions disabled by default.

## `/api/sandboxes` returns 404

This is expected. Kubernetes/Docker sandbox management is disabled in this HFS demo profile.

## Need file writing

Do not simply enable all write tools in a public Space. Prefer a narrow design:

1. Add `file:write` group.
2. Add only `write_file` if required.
3. Restrict prompts/config so writes occur under a dedicated workspace.
4. Keep `bash` disabled.
5. Test with untrusted inputs.

## Need Docker or Kubernetes sandbox

This project does not attempt Docker-in-Docker or DooD. Use one of these routes instead:

- run DeerFlow official Docker/Kubernetes deployment outside HFS;
- keep HFS as UI/Gateway only and call an external authenticated sandbox control plane;
- implement a custom remote sandbox provider with HTTPS, auth, quotas and audit logs.
