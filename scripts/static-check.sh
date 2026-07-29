#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

bash -n hfs/bin/entrypoint.sh hfs/bin/healthcheck.sh scripts/smoke-test.sh scripts/static-check.sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from pathlib import Path

for path in (
    "hfs/services/ops_service.py",
    "hfs/services/admin_service.py",
    "scripts/service-contract-test.py",
    "scripts/export_hfs_space_bundle.py",
    "scripts/test_hfs_exporter.py",
):
    compile(Path(path).read_text(encoding="utf-8"), path, "exec")
PY
PYTHONDONTWRITEBYTECODE=1 python3 scripts/service-contract-test.py
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts.test_hfs_exporter

python3 - <<'PY'
from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


def fail(message: str) -> None:
    print(f"static-check: {message}", file=sys.stderr)
    raise SystemExit(1)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def exact_path_exists(path: str) -> bool:
    target = Path(path)
    parent = target.parent if str(target.parent) != "" else Path(".")
    if not parent.exists():
        return False
    return target.name in {child.name for child in parent.iterdir()}


required_paths = [
    "README.md",
    "Dockerfile",
    "hfs-dev.toml",
    "hfs-dev.candidate.toml",
    ".env.example",
    "Makefile",
    "hfs/bin/entrypoint.sh",
    "hfs/bin/healthcheck.sh",
    "hfs/config/config.hfs.yaml",
    "hfs/config/extensions_config.json",
    "hfs/config/next.hfs.config.js",
    "hfs/nginx/nginx.conf",
    "hfs/supervisor/supervisord.conf",
    "hfs/services/ops_service.py",
    "hfs/services/admin_service.py",
    "scripts/smoke-test.sh",
    "scripts/service-contract-test.py",
    "scripts/hf_space_sync.py",
    "hfs-space-bundle.json",
    ".github/workflows/deploy-hfs-formal.yml",
    "docs/architecture.md",
    "docs/configuration.md",
    "docs/deployment.md",
    "docs/development.md",
    "docs/ops-runbook.md",
    "docs/security.md",
    "docs/upstream-mapping.md",
]
for item in required_paths:
    require(Path(item).exists(), f"missing required path: {item}")

for old_path in [
    "hfs/entrypoint.sh",
    "hfs/healthcheck.sh",
    "hfs/config.hfs.yaml",
    "hfs/extensions_config.json",
    "hfs/nginx.conf",
    "hfs/supervisord.conf",
    "hfs/ops_service.py",
    "hfs/admin_service.py",
    "docs/ARCHITECTURE.md",
    "docs/DEPLOY_HF_SPACE.md",
    "docs/ENV_REFERENCE.md",
    "docs/LOCAL_TEST.md",
    "docs/OFFICIAL_DEPLOYMENT_MAPPING.md",
    "docs/SECURITY.md",
    "docs/TROUBLESHOOTING.md",
    "docs/V0_QUICK_DEV.md",
]:
    require(not exact_path_exists(old_path), f"old layout path still exists: {old_path}")

require(not Path("cloud/hfs").exists(), "Pattern A repo must not move Space root into cloud/hfs")

readme = read("README.md")
dockerfile = read("Dockerfile")
nginx = read("hfs/nginx/nginx.conf")
healthcheck = read("hfs/bin/healthcheck.sh")
smoke = read("scripts/smoke-test.sh")
formal_workflow = read(".github/workflows/deploy-hfs-formal.yml")
entrypoint = read("hfs/bin/entrypoint.sh")
supervisor = read("hfs/supervisor/supervisord.conf")
ops = read("hfs/services/ops_service.py")
admin = read("hfs/services/admin_service.py")
config = read("hfs/config/config.hfs.yaml")
next_config = read("hfs/config/next.hfs.config.js")
hf_vars = read("examples/hf-space-variables.example.env")
makefile = read("Makefile")
manifest = read("hfs-dev.toml")
manifest_data = tomllib.loads(manifest)
candidate_manifest_data = tomllib.loads(read("hfs-dev.candidate.toml"))

frontmatter = readme.split("---", 2)
require(len(frontmatter) >= 3, "README.md must start with HF metadata frontmatter")
metadata = frontmatter[1]
require(re.search(r"(?m)^sdk:\s*docker\s*$", metadata) is not None, "README metadata must set sdk: docker")
require(re.search(r"(?m)^app_port:\s*7860\s*$", metadata) is not None, "README metadata must set app_port: 7860")

require("EXPOSE 7860" in dockerfile, "Dockerfile must expose 7860")
require("CMD /home/user/app/hfs/bin/healthcheck.sh" in dockerfile, "Dockerfile healthcheck must use hfs/bin/healthcheck.sh")
require('ENTRYPOINT ["tini", "--", "/home/user/app/hfs/bin/entrypoint.sh"]' in dockerfile, "Dockerfile entrypoint must use hfs/bin/entrypoint.sh")
docker_ref_match = re.search(r"(?m)^ARG DEERFLOW_REF=([0-9a-f]{40})$", dockerfile)
require(docker_ref_match is not None, "Dockerfile DEERFLOW_REF default must be a full commit SHA")
docker_ref = docker_ref_match.group(1)
make_ref_match = re.search(r"(?m)^DEERFLOW_REF \?= ([0-9a-f]{40})$", makefile)
require(make_ref_match is not None and make_ref_match.group(1) == docker_ref, "Makefile DEERFLOW_REF must match the Dockerfile pin")
require('git fetch --depth 1 origin "${DEERFLOW_REF}"' in dockerfile, "Dockerfile must shallow-fetch branch, tag, or commit refs")
require('git clone --depth 1 --branch "${DEERFLOW_REF}"' not in dockerfile, "Dockerfile must not treat a commit SHA as a clone branch")
require(".deerflow-upstream-version" in dockerfile and ".deerflow-upstream-ref" in dockerfile, "Dockerfile must record upstream ref and version metadata")
require("DEER_FLOW_OPS_SESSION_TTL_SECONDS=3600" in dockerfile, "Dockerfile must expose ops session ttl default")
require("DEER_FLOW_OPS_COOKIE_SECURE=auto" in dockerfile, "Dockerfile must expose ops cookie secure default")
require("DEER_FLOW_OPS_LOG_DIR=/data/deer-flow/logs" in dockerfile, "Dockerfile must expose ops log dir default")
require("pnpm typecheck" in dockerfile and "NODE_OPTIONS=--max-old-space-size=3072" in dockerfile, "Dockerfile must run bounded frontend typecheck separately")
require("next.config.upstream.js" in dockerfile and "next.hfs.config.js" in dockerfile, "Dockerfile must install the HFS Next build overlay")
require("cpus: 2" in next_config, "HFS Next config must match cpu-basic worker capacity")
require("webpackMemoryOptimizations: true" in next_config, "HFS Next config must reduce Webpack peak memory")
require("ignoreBuildErrors: true" in next_config, "HFS Next config must skip only the duplicate in-build typecheck")
require("--build-arg DEERFLOW_REF=$(DEERFLOW_REF)" in makefile, "Makefile build must pass DEERFLOW_REF")
expected_manifest = {
    "standard": "2.0",
    "project": "DeerFlow-all-in-one-HFS",
    "space": "BlueSkyXN/DeerFlow-all-in-one-HFS",
    "sovereignty": "port",
    "lane": "source",
    "version_source": "commit",
}
expected_deviations = [
    "business-image = UV_IMAGE is a version-pinned build-tool source and is not the DeerFlow business or runtime image"
]
for key, value in expected_manifest.items():
    require(manifest_data.get(key) == value, f"hfs-dev.toml {key} must be {value!r}")

require(
    candidate_manifest_data.get("space") == "BlueSkyXN/DeerFlow-all-in-one-HFS-v2-candidate",
    "candidate manifest must select the fixed private candidate Space",
)
for key in sorted(set(manifest_data) | set(candidate_manifest_data)):
    if key != "space":
        require(
            manifest_data.get(key) == candidate_manifest_data.get(key),
            f"candidate manifest differs from production at {key}",
        )

classification_fields = ("local_only", "secrets", "optional_secrets", "variables")
allowed_manifest_fields = set(expected_manifest) | set(classification_fields) | {"deviations"}
require(
    set(manifest_data) == allowed_manifest_fields,
    "hfs-dev.toml must contain only HFS v2 fields and key classifications",
)
require(
    manifest_data.get("deviations") == expected_deviations,
    "hfs-dev.toml deviations must document only the reviewed build-tool image",
)
require(
    {"HF_TOKEN", "GH_TOKEN"}.issubset(set(manifest_data["local_only"])),
    "HFS control credentials must remain local_only",
)
require(
    re.search(r"(?:hf_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,})", manifest)
    is None,
    "hfs-dev.toml must register names only, never token values",
)

classified_keys: dict[str, list[str]] = {}
for field in classification_fields:
    keys = manifest_data.get(field)
    require(isinstance(keys, list) and keys, f"hfs-dev.toml {field} must be a non-empty key list")
    require(all(isinstance(key, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) for key in keys), f"hfs-dev.toml {field} contains an invalid environment key")
    require(len(keys) == len(set(keys)), f"hfs-dev.toml {field} contains duplicate environment keys")
    classified_keys[field] = keys

for left, right in (
    ("local_only", "secrets"),
    ("local_only", "optional_secrets"),
    ("local_only", "variables"),
    ("secrets", "optional_secrets"),
    ("secrets", "variables"),
    ("optional_secrets", "variables"),
):
    overlap = sorted(set(classified_keys[left]) & set(classified_keys[right]))
    require(not overlap, f"hfs-dev.toml {left} and {right} must be mutually exclusive: {overlap}")

env_example_keys: list[str] = []
for line_number, line in enumerate(read(".env.example").splitlines(), start=1):
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        continue
    match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=", stripped)
    require(match is not None, f".env.example:{line_number} must contain a key name with no value")
    env_example_keys.append(match.group(1))
require(len(env_example_keys) == len(set(env_example_keys)), ".env.example must not repeat keys")
require(
    set(env_example_keys)
    == set(classified_keys["secrets"])
    | set(classified_keys["optional_secrets"])
    | set(classified_keys["variables"]),
    ".env.example must contain every HFS secret and variable key, and no local-only key",
)
gitignore = read(".gitignore")
for ignore_rule in (".env", ".env.*", "!.env.example", "config.toml", "local/"):
    require(re.search(rf"(?m)^{re.escape(ignore_rule)}$", gitignore) is not None, f".gitignore must declare {ignore_rule}")

configuration_docs = read("docs/configuration.md")
for fragment in ("hf_space_sync.py diff", "hf_space_sync.py push", "readback", "没有需要分发的"):
    require(fragment in configuration_docs, f"configuration docs must explain {fragment!r}")

require("listen 7860 default_server;" in nginx, "Nginx must listen on 7860")
require("log_format hfs_safe" in nginx and "$request_method $uri $server_protocol" in nginx, "Nginx access logs must omit query strings")
require("$request_uri" not in nginx and "$args" not in nginx and "$is_args" not in nginx, "Nginx must not log or preserve query strings on control surfaces")
require("/nginx-health" in nginx, "Nginx must expose a direct liveness endpoint")
require("location = /healthz" in nginx and "proxy_pass http://deerflow_ops/readyz" in nginx, "Nginx /healthz must route to ops readiness")
require("return 308 /_ops/;" in nginx and "return 308 /_admin/;" in nginx, "Nginx control-surface redirects must drop query strings")
require("return 404" in nginx and "/api/sandboxes" in nginx, "Nginx must keep /api/sandboxes disabled")
require("client_max_body_size 2M;" in nginx, "Nginx default body limit must stay small")
require("client_max_body_size 16k;" in nginx, "Nginx ops route must use a small body limit")
require("client_max_body_size 64k;" in nginx, "Nginx admin route must use a small body limit")
require("client_max_body_size 100M;" in nginx, "Nginx upload route must keep explicit upload body limit")
require("limit_except GET" in nginx, "Nginx ops route must reject non-GET methods")
require("limit_except GET POST" in nginx, "Nginx admin route must reject unexpected methods")
require("http://127.0.0.1:7860/_ops/readyz" in healthcheck, "healthcheck must go through Nginx /_ops/readyz")
require('BASE_URL="${1:-http://localhost:7860}"' in smoke, "smoke default must target localhost:7860")
require("check /nginx-health 200" in smoke, "smoke must check direct Nginx liveness")
require("check /healthz 200" in smoke, "smoke must check public HFS healthz")
require("/_ops/system" in smoke and "/_ops/metrics" in smoke and "/_ops/errors" in smoke, "smoke must cover protected ops diagnostics when token is configured")
require("/_admin/api/actions/run-health-checks" in smoke, "smoke must cover admin read-only action when admin is enabled")
require("EXPECTED_DEERFLOW_REF" in smoke and "upstream SHA" in smoke, "smoke must verify the deployed upstream pin")
require("FORMAL_SPACE: BlueSkyXN/DeerFlow-all-in-one-HFS" in formal_workflow, "formal workflow must hard-code the canonical Space")
require("environment: hfs-production" in formal_workflow, "formal workflow must use the scoped production environment")
require("PUBLISH_FORMAL" in formal_workflow, "formal workflow must require exact upload confirmation")
require("export_hfs_space_bundle.py export" in formal_workflow, "formal workflow must use the strict exporter")
require('--source-commit "$SOURCE_REF"' in formal_workflow, "formal workflow must authorize every verifier against the locked source commit")
require('HF_CLI_VERSION: "1.5.0"' in formal_workflow, "formal workflow must pin huggingface_hub 1.5.0")
require('HF_CLI_CLICK_VERSION: "8.3.1"' in formal_workflow, "formal workflow must pin click 8.3.1")
require("huggingface_hub==${HF_CLI_VERSION}" in formal_workflow, "formal workflow must install the pinned Hugging Face client")
require("click==${HF_CLI_CLICK_VERSION}" in formal_workflow, "formal workflow must install the direct module CLI dependency")
require("python3 -m huggingface_hub.cli.hf --help" in formal_workflow, "formal workflow must exercise the module CLI")
require("python3 -m huggingface_hub.cli.hf upload --help" in formal_workflow, "formal workflow must exercise the upload command")
require("deployed_revision = info.sha" in formal_workflow, "formal workflow must capture the immutable uploaded Space revision")
require("revision=deployed_revision" in formal_workflow, "formal workflow must read back the immutable uploaded revision")
require('runtime.stage == "RUNNING"' in formal_workflow, "formal workflow must wait for a running canonical Space")
require('runtime.raw.get("sha") == deployed_revision' in formal_workflow, "formal workflow must bind runtime to the uploaded revision")
require('runtime.stage in {"BUILD_ERROR", "RUNTIME_ERROR"}' in formal_workflow, "formal workflow must fail closed on Space build and runtime errors")

require("/home/user/app/hfs/config/config.hfs.yaml" in entrypoint, "entrypoint must read managed config from hfs/config")
require("/home/user/app/hfs/config/extensions_config.json" in entrypoint, "entrypoint must read extensions config from hfs/config")
require("/home/user/app/hfs/supervisor/supervisord.conf" in entrypoint, "entrypoint must start hfs/supervisor config")
require(".hfs-persistence-probe" in entrypoint, "entrypoint must write persistence probe")
require('DEER_FLOW_DB_DIR="${DEER_FLOW_DB_DIR:-${DEER_FLOW_HOME}/data}"' in entrypoint, "entrypoint must place the database under the resolved runtime home")
require('DEER_FLOW_DB_DIR="${DEER_FLOW_HOME}/data"' in entrypoint, "entrypoint must move the database path when /data falls back")
require("AUTH_JWT_SECRET" in entrypoint and ".jwt_secret" in entrypoint, "entrypoint must manage the current DeerFlow JWT secret")
require("BETTER_AUTH_SECRET as the AUTH_JWT_SECRET compatibility source" in entrypoint, "entrypoint must label BETTER_AUTH_SECRET as legacy compatibility")

require("config_version: 29" in config, "managed config must match the reviewed upstream schema version")
require("backend: sqlite" in config and "sqlite_dir: $DEER_FLOW_DB_DIR" in config, "managed config must persist SQLite under DEER_FLOW_DB_DIR")
require("pool_recycle: 300" in config and "command_timeout: 30" in config, "managed config must declare schema v29 database defaults")
require("checkpoint_channel_mode: full" in config, "managed config must keep the reviewed full checkpoint mode")
require("agent_storage:" in config and "backend: file" in config, "managed config must keep single-node agent storage explicit")
require("llm_call:" in config and "max_concurrent_calls: 0" in config, "managed config must make the reviewed LLM concurrency default explicit")
require("auth:" in config and "allow_registration: false" in config, "managed config must disable public local self-registration")
require("authorization:" in config and "enabled: false" in config, "managed config must keep upstream authorization opt-in")
require("registration_enabled" in smoke, "smoke must verify the public local registration policy")

require("/home/user/app/hfs/services/ops_service.py" in supervisor, "supervisor must start moved ops service")
require("/home/user/app/hfs/services/admin_service.py" in supervisor, "supervisor must start moved admin service")
require("/home/user/app/hfs/nginx/nginx.conf" in supervisor, "supervisor must start moved nginx config")

require("ops-write-test" not in ops, "ops readiness must not write request-time probe")
require("persistence_probe" in ops, "ops readiness must check entrypoint persistence probe")
require("readiness(include_details=False)" in ops, "public ops readiness must use coarse detail")
require("OPS_SESSION_COOKIE" in ops, "ops service must support signed HttpOnly session cookies")
require("SameSite=Strict" in ops, "ops session cookie must use SameSite=Strict")
require('query.get("token"' not in ops, "ops service must not accept secrets in query strings")
require("logs_payload" in ops and "errors_payload" in ops, "ops service must expose protected logs/errors diagnostics")
require("redact_text" in ops, "ops logs diagnostics must redact configured secret values")
require("AUTH_JWT_SECRET" in ops and "DATABASE_URL" in ops, "ops redaction must cover current auth and database secrets")
require("metrics_payload" in ops and "system_payload" in ops and "persistence_payload" in ops, "ops service must expose protected diagnostics")
require('upstream_metadata("version")' in ops and 'upstream_metadata("ref")' in ops, "ops version must report pinned upstream metadata")
require("localStorage" not in ops, "ops shell must not persist ops tokens in browser storage")
require("Content-Security-Policy" in ops, "ops service must emit security headers")
require("X-DeerFlow-Admin-Intent" in admin, "admin POSTs must require intent header")
require("X-DeerFlow-Admin-Confirm" in admin, "admin POSTs must require confirmation header")
require("admin-actions.jsonl" in admin, "admin actions must write audit log")
require("actions_payload" in admin and "audit_payload" in admin, "admin service must expose actions and audit APIs")
require("run-health-checks" in admin, "admin service must include read-only health-check action")
require("MAX_AUDIT_BYTES" in admin and "redact_payload" in admin, "admin audit reads must be bounded and redacted")
require('200 if data["status"] == "ok" else 503' in admin, "admin health checks must return a failing status when degraded")
require("Fixed actions" not in admin, "public admin shell must not disclose write action UI")
require("localStorage" not in admin, "public admin shell must not persist admin tokens in browser storage")
require("Content-Security-Policy" in admin, "admin service must emit security headers")
require("DEER_FLOW_ADMIN_ENABLED=false" in hf_vars, "HF variables example must keep admin APIs disabled by default")
require("DEERFLOW_REF=" not in hf_vars, "HF runtime variables must not pretend to override Docker build args")

print("static-check: ok")
PY
