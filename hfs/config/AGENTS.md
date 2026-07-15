# hfs/config navigation card

`hfs/config/` contains managed DeerFlow runtime config copied into `$DEER_FLOW_HOME`.
Read this after `hfs/AGENTS.md` before changing models, tools, sandbox, uploads, loop detection, token usage, or MCP/extensions.
Key files: `config.hfs.yaml`, `extensions_config.json`.

## Local invariants

- With `DEER_FLOW_MANAGED_CONFIG=true`, startup overwrites `$DEER_FLOW_CONFIG_PATH` from `config.hfs.yaml`.
- The managed config version must match the reviewed upstream schema, and SQLite must remain explicit under `$DEER_FLOW_DB_DIR` rather than a relative source-checkout path.
- At least one default model must remain usable. Current config uses OpenAI-compatible `langchain_openai:ChatOpenAI` entries and `$OPENAI_API_KEY`.
- Public demo tools stay conservative: web plus file read-oriented tools only.
- `sandbox.use` remains `deerflow.sandbox.local:LocalSandboxProvider` and `allow_host_bash` remains `false` unless the user explicitly approves a different public-demo posture.
- `extensions_config.json` is empty for `mcpServers` and `skills`; remote extensions change the trust boundary.

## Local rules

- Model/provider changes must keep env names aligned with examples, env docs, and `README.md`.
- Tool, sandbox, upload, or extension changes must be checked against security docs.
- Keep placeholders as environment references such as `$OPENAI_API_KEY`; never write real API keys or private endpoints.

## Do not

- Do not enable `bash`, unrestricted `file:write`, Docker sandbox, Kubernetes provisioner, or document auto-conversion for a public demo without explicit user approval and documentation updates.
- Do not hard-code private model gateways, tokens, bucket URLs, or machine paths.
- Do not treat comments in `config.hfs.yaml` as dead text; they guide runtime safety.

## Validation

- `make static-check` is the default no-Docker validation.
- Material config behavior changes need `make build`, `make run`, then `make smoke` when Docker, network, and credentials are available.
- For model/provider changes, also verify the relevant docs/examples list the same env variables without exposing real values.
