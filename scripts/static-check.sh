#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

bash -n hfs/bin/entrypoint.sh hfs/bin/healthcheck.sh scripts/smoke-test.sh scripts/static-check.sh
python3 -m py_compile hfs/services/ops_service.py hfs/services/admin_service.py

python3 - <<'PY'
from __future__ import annotations

import re
import sys
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
    "Makefile",
    "hfs/bin/entrypoint.sh",
    "hfs/bin/healthcheck.sh",
    "hfs/config/config.hfs.yaml",
    "hfs/config/extensions_config.json",
    "hfs/nginx/nginx.conf",
    "hfs/supervisor/supervisord.conf",
    "hfs/services/ops_service.py",
    "hfs/services/admin_service.py",
    "scripts/smoke-test.sh",
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
entrypoint = read("hfs/bin/entrypoint.sh")
supervisor = read("hfs/supervisor/supervisord.conf")
ops = read("hfs/services/ops_service.py")
admin = read("hfs/services/admin_service.py")
hf_vars = read("examples/hf-space-variables.example.env")
makefile = read("Makefile")
manifest = read("hfs-dev.toml")

frontmatter = readme.split("---", 2)
require(len(frontmatter) >= 3, "README.md must start with HF metadata frontmatter")
metadata = frontmatter[1]
require(re.search(r"(?m)^sdk:\s*docker\s*$", metadata) is not None, "README metadata must set sdk: docker")
require(re.search(r"(?m)^app_port:\s*7860\s*$", metadata) is not None, "README metadata must set app_port: 7860")

require("EXPOSE 7860" in dockerfile, "Dockerfile must expose 7860")
require("CMD /home/user/app/hfs/bin/healthcheck.sh" in dockerfile, "Dockerfile healthcheck must use hfs/bin/healthcheck.sh")
require('ENTRYPOINT ["tini", "--", "/home/user/app/hfs/bin/entrypoint.sh"]' in dockerfile, "Dockerfile entrypoint must use hfs/bin/entrypoint.sh")
require("ARG DEERFLOW_REF=main" in dockerfile, "Dockerfile must expose DEERFLOW_REF build surface")
require("--build-arg DEERFLOW_REF=$(DEERFLOW_REF)" in makefile, "Makefile build must pass DEERFLOW_REF")
require('standard = "hfs-dev"' in manifest, "hfs-dev.toml must declare hfs-dev standard")
require('pattern = "A"' in manifest, "hfs-dev.toml must declare Pattern A")
require('runtime_mode = "source-fetch"' in manifest, "hfs-dev.toml must declare source-fetch runtime mode")
require('space_root_mode = "repo-root"' in manifest, "hfs-dev.toml must declare repo-root space root")
require('release_pin_required = true' in manifest, "hfs-dev.toml must require release pinning")
require("DEERFLOW_REF=<deer-flow upstream commit SHA>" in manifest, "hfs-dev.toml must declare DEERFLOW_REF commit SHA pin surface")

require("listen 7860 default_server;" in nginx, "Nginx must listen on 7860")
require("return 404" in nginx and "/api/sandboxes" in nginx, "Nginx must keep /api/sandboxes disabled")
require("http://127.0.0.1:7860/_ops/readyz" in healthcheck, "healthcheck must go through Nginx /_ops/readyz")
require('BASE_URL="${1:-http://localhost:7860}"' in smoke, "smoke default must target localhost:7860")

require("/home/user/app/hfs/config/config.hfs.yaml" in entrypoint, "entrypoint must read managed config from hfs/config")
require("/home/user/app/hfs/config/extensions_config.json" in entrypoint, "entrypoint must read extensions config from hfs/config")
require("/home/user/app/hfs/supervisor/supervisord.conf" in entrypoint, "entrypoint must start hfs/supervisor config")
require(".hfs-persistence-probe" in entrypoint, "entrypoint must write persistence probe")

require("/home/user/app/hfs/services/ops_service.py" in supervisor, "supervisor must start moved ops service")
require("/home/user/app/hfs/services/admin_service.py" in supervisor, "supervisor must start moved admin service")
require("/home/user/app/hfs/nginx/nginx.conf" in supervisor, "supervisor must start moved nginx config")

require("ops-write-test" not in ops, "ops readiness must not write request-time probe")
require("persistence_probe" in ops, "ops readiness must check entrypoint persistence probe")
require("X-DeerFlow-Admin-Intent" in admin, "admin POSTs must require intent header")
require("X-DeerFlow-Admin-Confirm" in admin, "admin POSTs must require confirmation header")
require("admin-actions.jsonl" in admin, "admin actions must write audit log")
require("DEER_FLOW_ADMIN_ENABLED=false" in hf_vars, "HF variables example must keep admin disabled by default")

print("static-check: ok")
PY
