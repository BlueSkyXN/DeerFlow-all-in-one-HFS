# Deploy to Hugging Face Docker Space

## 1. Space target

Target Space:

```text
https://huggingface.co/spaces/BlueSkyXN/DeerFlow-all-in-one-HFS
https://blueskyxn-deerflow-all-in-one-hfs.hf.space
```

The repository root contains the Docker Space card front matter:

```yaml
---
sdk: docker
app_port: 7860
---
```

## 2. Push repository content

Push the same commit to GitHub and the Hugging Face Space repository:

```bash
git push origin main
git push hf main
```

If the `hf` remote does not exist:

```bash
git remote add hf https://huggingface.co/spaces/BlueSkyXN/DeerFlow-all-in-one-HFS
git push hf main
```

## 3. Configure hardware

Recommended starting point:

- CPU Upgrade for smoother builds/runtime.
- GPU is usually unnecessary if you use external LLM APIs.

The smallest CPU tier can build slowly because the image installs Python and Next.js dependencies from upstream DeerFlow.

## 4. Configure Variables

Add these in Space Settings -> Variables:

```bash
DEER_FLOW_ENV=hf-space
DEER_FLOW_PROJECT_ROOT=/home/user/app/deer-flow
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

These are also shown in `examples/hf-space-variables.example.env`.

## 5. Configure Secrets

At minimum, add one model provider secret that matches your config.

For OpenRouter default config:

```bash
OPENROUTER_API_KEY=...
```

For OpenAI direct config:

```bash
OPENAI_API_KEY=...
```

Recommended security secrets:

```bash
BETTER_AUTH_SECRET=generate-a-long-random-string
DEER_FLOW_INTERNAL_AUTH_TOKEN=generate-another-long-random-string
DEER_FLOW_OPS_TOKEN=generate-ops-token
DEER_FLOW_ADMIN_TOKEN=generate-admin-token
```

Optional search/fetch providers:

```bash
TAVILY_API_KEY=...
SERPER_API_KEY=...
JINA_API_KEY=...
EXA_API_KEY=...
FIRECRAWL_API_KEY=...
INFOQUEST_API_KEY=...
```

Do not commit real secrets into the repository.

## 6. Attach persistent storage

Attach a Hugging Face Storage Bucket to:

```text
/data
```

Without persistent storage, `/data/deer-flow/config.yaml`, generated auth secrets, uploads, and threads may be lost after restart.

## 7. First boot behavior

On first startup, `hfs/entrypoint.sh` creates:

```text
/data/deer-flow/config.yaml
/data/deer-flow/extensions_config.json
/data/deer-flow/.better-auth-secret       # only if BETTER_AUTH_SECRET absent
/data/deer-flow/.internal-auth-token      # only if DEER_FLOW_INTERNAL_AUTH_TOKEN absent
/data/deer-flow/threads/
/data/deer-flow/uploads/
/data/deer-flow/logs/
```

If you want to edit the model or tools, edit `/data/deer-flow/config.yaml` in a persistent runtime or bake a modified `hfs/config.hfs.yaml` into the repository.

## 8. Verify

After Space starts, check:

```text
https://blueskyxn-deerflow-all-in-one-hfs.hf.space/health
https://blueskyxn-deerflow-all-in-one-hfs.hf.space/_ops/healthz
https://blueskyxn-deerflow-all-in-one-hfs.hf.space/_ops/readyz
https://blueskyxn-deerflow-all-in-one-hfs.hf.space/openapi.json
https://blueskyxn-deerflow-all-in-one-hfs.hf.space/api/v1/auth/setup-status
```

Token-protected checks:

```bash
curl -H "Authorization: Bearer $DEER_FLOW_OPS_TOKEN" \
  https://blueskyxn-deerflow-all-in-one-hfs.hf.space/_ops/status

curl -H "Authorization: Bearer $DEER_FLOW_ADMIN_TOKEN" \
  https://blueskyxn-deerflow-all-in-one-hfs.hf.space/_admin/api/status
```

The UI should load at the Space root. On a fresh DeerFlow data directory, visit `/setup` through the UI to create the first admin user before normal chat flows.

## 9. Suggested visibility

Use **Private** for early testing. Use **Protected** if you want controlled sharing.

Avoid fully public deployment unless you have reviewed:

- enabled tools;
- file write paths;
- model cost exposure;
- rate limits;
- uploads;
- authentication/session behavior;
- logs and secrets handling;
- `/_admin` action switches.

## 10. Pin DeerFlow version

This project defaults to `DEERFLOW_REF=main`. For stability, set a commit SHA at build time.

In Hugging Face, add a build Variable if desired:

```bash
DEERFLOW_REF=<commit-sha>
```

Or edit the Dockerfile default.
