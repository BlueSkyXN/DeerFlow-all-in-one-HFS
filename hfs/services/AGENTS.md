# hfs/services navigation card

`hfs/services/` contains Python stdlib ops/admin services exposed through Nginx.
Read this after `hfs/AGENTS.md` before changing endpoints, token checks, payloads, admin actions, audit logging, or security headers.
Key files: `ops_service.py`, `admin_service.py`.

## Local invariants

- Services bind to `127.0.0.1` only; public access goes through Nginx.
- Keep implementation dependency-free unless the Docker image and docs are deliberately updated.
- Ops public endpoints are coarse: `/_ops/healthz` and `/_ops/readyz`; detailed endpoints require token auth.
- Ops authentication accepts headers or the signed path-scoped session cookie, never query-string tokens.
- Ops/admin config responses may report safe values and secret presence, never raw secret values.
- Admin APIs and write actions default off through `DEER_FLOW_ADMIN_ENABLED=false` and `DEER_FLOW_ADMIN_ACTIONS_ENABLED=false`.
- Admin write actions require token auth, enabled actions, intent/confirm headers, and audit logging.
- The public admin HTML shell must not persist tokens or reveal write-action capability by itself.
- Responses should keep no-store cache, nosniff, referrer, frame, and restrictive CSP headers.

## Local rules

- New endpoints must define public/token/action protection; Nginx limits must match.
- Redaction changes must be reviewed against `docs/security.md` and `scripts/static-check.sh`.
- Log and audit reads must remain allowlisted, byte-bounded, response-bounded, and secret-redacted.
- Keep command execution fixed-list only. Do not add arbitrary shell command execution.

## Do not

- Do not expose `.env.local`, raw env values, generated auth secrets, private URLs, persistent config, or secret-bearing logs.
- Do not enable admin write actions by default in code, env examples, or docs.
- Do not add browser localStorage/sessionStorage token persistence to admin UI.

## Validation

- `python3 -m py_compile hfs/services/ops_service.py hfs/services/admin_service.py` checks Python syntax.
- `make static-check` is the default no-Docker validation and runs `scripts/service-contract-test.py`.
- Endpoint behavior changes should also run `make smoke` when a service is running; admin protected checks need the relevant token env vars.
