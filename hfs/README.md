# HFS runtime layer

`hfs/` contains the runtime glue copied into the Docker image at `/home/user/app/hfs`.
This repository is a Pattern A HFS port repository, so the repository root remains the Space root and `hfs/` is only the internal guardrail layer.

```text
hfs/
├─ bin/           entrypoint and Docker healthcheck
├─ config/        managed DeerFlow and extensions config
├─ nginx/         public reverse proxy on port 7860
├─ supervisor/    process orchestration
└─ services/      ops/admin Python stdlib services
```

Keep ops read-only. Keep admin disabled by default; enabling admin actions requires an explicit maintenance window, token auth, intent/confirm headers, and audit logging.
