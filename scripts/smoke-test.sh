#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL="${1:-http://localhost:7860}"
OPS_TOKEN="${DEER_FLOW_OPS_TOKEN:-${OPS_TOKEN:-}}"
ADMIN_TOKEN="${DEER_FLOW_ADMIN_TOKEN:-${ADMIN_TOKEN:-}}"
ADMIN_ENABLED="${DEER_FLOW_ADMIN_ENABLED:-${ADMIN_ENABLED:-false}}"

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

check /health 200
check /openapi.json 200
check /api/v1/auth/setup-status 200
check /api/sandboxes 404
check /_ops/healthz 200
check /_ops/readyz 200
check /_admin/ 200

if [ -n "${OPS_TOKEN}" ]; then
  check_auth /_ops/status "Bearer ${OPS_TOKEN}" "Authorization"
fi

case "${ADMIN_ENABLED}" in
  1|true|TRUE|yes|YES|on|ON)
    if [ -n "${ADMIN_TOKEN}" ]; then
      check_auth /_admin/api/status "Bearer ${ADMIN_TOKEN}" "Authorization"
    fi
    ;;
esac

echo "Smoke test passed."
