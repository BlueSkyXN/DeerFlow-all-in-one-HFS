#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE_URL="${1:-http://localhost:7860}"
OPS_TOKEN="${DEER_FLOW_OPS_TOKEN:-${OPS_TOKEN:-}}"
ADMIN_TOKEN="${DEER_FLOW_ADMIN_TOKEN:-${ADMIN_TOKEN:-}}"
ADMIN_ENABLED="${DEER_FLOW_ADMIN_ENABLED:-${ADMIN_ENABLED:-false}}"
EXPECTED_DEERFLOW_REF="${DEERFLOW_REF:-$(sed -n 's/^ARG DEERFLOW_REF=//p' "${REPO_ROOT}/Dockerfile" | head -n 1)}"

echo "Smoke testing ${BASE_URL}"

check() {
  local path="$1"
  local expected="${2:-200}"
  local code
  code="$(curl -fsS -o /tmp/deerflow-all-in-one-hfs-smoke.out -w '%{http_code}' "${BASE_URL}${path}" || true)"
  if [ "${code}" != "${expected}" ]; then
    echo "FAIL ${path}: expected HTTP ${expected}, got ${code}" >&2
    cat /tmp/deerflow-all-in-one-hfs-smoke.out >&2 || true
    exit 1
  fi
  echo "OK   ${path} -> ${code}"
}

check_auth() {
  local path="$1"
  local token="$2"
  local header_name="$3"
  local code
  code="$(curl -fsS -H "${header_name}: ${token}" -o /tmp/deerflow-all-in-one-hfs-smoke.out -w '%{http_code}' "${BASE_URL}${path}" || true)"
  if [ "${code}" != "200" ]; then
    echo "FAIL ${path}: expected HTTP 200 with token, got ${code}" >&2
    cat /tmp/deerflow-all-in-one-hfs-smoke.out >&2 || true
    exit 1
  fi
  echo "OK   ${path} -> ${code}"
}

check_post_auth() {
  local path="$1"
  local token="$2"
  local header_name="$3"
  local confirm="$4"
  local code
  code="$(curl -fsS \
    -X POST \
    -H "${header_name}: ${token}" \
    -H "X-DeerFlow-Admin-Intent: DeerFlow-HFS-Admin" \
    -H "X-DeerFlow-Admin-Confirm: ${confirm}" \
    -o /tmp/deerflow-all-in-one-hfs-smoke.out \
    -w '%{http_code}' \
    "${BASE_URL}${path}" || true)"
  if [ "${code}" != "200" ]; then
    echo "FAIL ${path}: expected HTTP 200 with token, got ${code}" >&2
    cat /tmp/deerflow-all-in-one-hfs-smoke.out >&2 || true
    exit 1
  fi
  echo "OK   ${path} -> ${code}"
}

check /nginx-health 200
check /healthz 200
check /health 200
check /openapi.json 200
check /api/v1/auth/setup-status 200
if ! python3 -c 'import json, sys; data = json.load(open(sys.argv[1], encoding="utf-8")); raise SystemExit(0 if data.get("registration_enabled") is False else 1)' /tmp/deerflow-all-in-one-hfs-smoke.out; then
  echo "FAIL /api/v1/auth/setup-status: expected registration_enabled=false" >&2
  cat /tmp/deerflow-all-in-one-hfs-smoke.out >&2 || true
  exit 1
fi
echo "OK   /api/v1/auth/setup-status registration_enabled -> false"
check /api/sandboxes 404
check /_ops/healthz 200
check /_ops/readyz 200
check /_admin/ 200

if [ -n "${OPS_TOKEN}" ]; then
  check_auth /_ops/status "${OPS_TOKEN}" "X-Ops-Token"
  check_auth /_ops/health "${OPS_TOKEN}" "X-Ops-Token"
  check_auth /_ops/system "${OPS_TOKEN}" "X-Ops-Token"
  check_auth /_ops/persistence "${OPS_TOKEN}" "X-Ops-Token"
  check_auth /_ops/version "${OPS_TOKEN}" "X-Ops-Token"
  if [ -n "${EXPECTED_DEERFLOW_REF}" ] && ! grep -Fq "\"upstream_sha\": \"${EXPECTED_DEERFLOW_REF}\"" /tmp/deerflow-all-in-one-hfs-smoke.out; then
    echo "FAIL /_ops/version: expected upstream SHA ${EXPECTED_DEERFLOW_REF}" >&2
    cat /tmp/deerflow-all-in-one-hfs-smoke.out >&2 || true
    exit 1
  fi
  echo "OK   /_ops/version upstream SHA -> ${EXPECTED_DEERFLOW_REF}"
  check_auth /_ops/metrics "${OPS_TOKEN}" "X-Ops-Token"
  check_auth /_ops/errors "${OPS_TOKEN}" "X-Ops-Token"
fi

case "${ADMIN_ENABLED}" in
  1|true|TRUE|yes|YES|on|ON)
    if [ -n "${ADMIN_TOKEN}" ]; then
      check_auth /_admin/api/status "Bearer ${ADMIN_TOKEN}" "Authorization"
      check_auth /_admin/api/actions "Bearer ${ADMIN_TOKEN}" "Authorization"
      check_auth "/_admin/api/audit?limit=5" "Bearer ${ADMIN_TOKEN}" "Authorization"
      check_post_auth /_admin/api/actions/run-health-checks "Bearer ${ADMIN_TOKEN}" "Authorization" "run-health-checks"
    fi
    ;;
esac

echo "Smoke test passed."
