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
manifest_data = tomllib.loads(manifest)

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
expected_manifest = {
    "schema_version": 2,
    "standard": "hfs-dev",
    "pattern": "A",
    "runtime_mode": "source-fetch",
    "space_root_mode": "repo-root",
    "hfs_dir": ".",
    "public_port": 7860,
    "release_pin_required": True,
}
for key, value in expected_manifest.items():
    require(manifest_data.get(key) == value, f"hfs-dev.toml {key} must be {value!r}")
require("release_pin_surfaces" not in manifest_data, "hfs-dev.toml v2 must use structured [[release_pins]]")
release_pins = manifest_data.get("release_pins")
require(isinstance(release_pins, list) and release_pins, "hfs-dev.toml must declare structured release_pins")
require(all(isinstance(pin, dict) for pin in release_pins), "hfs-dev.toml release_pins entries must be tables")
pins_by_name = {pin.get("name"): pin for pin in release_pins if isinstance(pin, dict)}
require(len(pins_by_name) == len(release_pins), "hfs-dev.toml release_pins names must be unique")
require(set(pins_by_name) == {"DEERFLOW_REF"}, "hfs-dev.toml release_pins must declare only DEERFLOW_REF")
deerflow_ref_pin = pins_by_name["DEERFLOW_REF"]
expected_ref_pin = {
    "type": "git_ref",
    "source": "Dockerfile ARG",
    "required_for_release": True,
    "dev_mutable_default_allowed": True,
    "release_requires_commit_sha": True,
}
for key, value in expected_ref_pin.items():
    require(deerflow_ref_pin.get(key) == value, f"hfs-dev.toml DEERFLOW_REF.{key} must be {value!r}")
require(
    isinstance(deerflow_ref_pin.get("description"), str) and "commit SHA" in deerflow_ref_pin["description"],
    "hfs-dev.toml DEERFLOW_REF must document commit SHA release requirement",
)

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
require("DEER_FLOW_ADMIN_ENABLED=false" in hf_vars, "HF variables example must keep admin APIs disabled by default")

print("static-check: ok")
PY
