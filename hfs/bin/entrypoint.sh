#!/usr/bin/env bash
set -Eeuo pipefail

log() {
  printf '[DeerFlow-all-in-one-HFS] %s\n' "$*" >&2
}

make_secret() {
  python - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
}

# Resolve writable runtime home. /data is persistent only when a HF Storage Bucket
# is attached; otherwise it is ephemeral, but still usually writable.
DEFAULT_DEER_FLOW_HOME="${DEER_FLOW_HOME:-/data/deer-flow}"
if mkdir -p "${DEFAULT_DEER_FLOW_HOME}" 2>/dev/null && touch "${DEFAULT_DEER_FLOW_HOME}/.write-test" 2>/dev/null; then
  rm -f "${DEFAULT_DEER_FLOW_HOME}/.write-test"
  export DEER_FLOW_HOME="${DEFAULT_DEER_FLOW_HOME}"
else
  log "WARN: ${DEFAULT_DEER_FLOW_HOME} is not writable; falling back to /tmp/deer-flow. Persistence will be lost."
  export DEER_FLOW_HOME=/tmp/deer-flow
  mkdir -p "${DEER_FLOW_HOME}"
fi

export HOME="${HOME:-/home/user}"
export DEER_FLOW_PROJECT_ROOT="${DEER_FLOW_PROJECT_ROOT:-/home/user/app/deer-flow}"
export DEER_FLOW_DB_DIR="${DEER_FLOW_DB_DIR:-${DEER_FLOW_HOME}/data}"
export DEER_FLOW_CONFIG_PATH="${DEER_FLOW_CONFIG_PATH:-${DEER_FLOW_HOME}/config.yaml}"
export DEER_FLOW_EXTENSIONS_CONFIG_PATH="${DEER_FLOW_EXTENSIONS_CONFIG_PATH:-${DEER_FLOW_HOME}/extensions_config.json}"
if [ "${DEER_FLOW_HOME}" != "/data/deer-flow" ]; then
  if [ "${DEER_FLOW_DB_DIR}" = "/data/deer-flow/data" ]; then
    export DEER_FLOW_DB_DIR="${DEER_FLOW_HOME}/data"
  fi
  if [ "${DEER_FLOW_CONFIG_PATH}" = "/data/deer-flow/config.yaml" ]; then
    export DEER_FLOW_CONFIG_PATH="${DEER_FLOW_HOME}/config.yaml"
  fi
  if [ "${DEER_FLOW_EXTENSIONS_CONFIG_PATH}" = "/data/deer-flow/extensions_config.json" ]; then
    export DEER_FLOW_EXTENSIONS_CONFIG_PATH="${DEER_FLOW_HOME}/extensions_config.json"
  fi
fi
export DEER_FLOW_SKILLS_PATH="${DEER_FLOW_SKILLS_PATH:-${DEER_FLOW_PROJECT_ROOT}/skills}"
export DEER_FLOW_MANAGED_CONFIG="${DEER_FLOW_MANAGED_CONFIG:-true}"
export GATEWAY_WORKERS="${GATEWAY_WORKERS:-1}"
export GATEWAY_ENABLE_DOCS="${GATEWAY_ENABLE_DOCS:-true}"
export DEER_FLOW_OPS_PORT="${DEER_FLOW_OPS_PORT:-8081}"
export DEER_FLOW_OPS_SESSION_TTL_SECONDS="${DEER_FLOW_OPS_SESSION_TTL_SECONDS:-3600}"
export DEER_FLOW_OPS_COOKIE_SECURE="${DEER_FLOW_OPS_COOKIE_SECURE:-auto}"
export DEER_FLOW_OPS_DEFAULT_CHECKS_ENABLED="${DEER_FLOW_OPS_DEFAULT_CHECKS_ENABLED:-true}"
export DEER_FLOW_OPS_LOG_DIR="${DEER_FLOW_OPS_LOG_DIR:-${DEER_FLOW_HOME}/logs}"
if [ "${DEER_FLOW_OPS_LOG_DIR}" = "/data/deer-flow/logs" ] && [ "${DEER_FLOW_HOME}" != "/data/deer-flow" ]; then
  export DEER_FLOW_OPS_LOG_DIR="${DEER_FLOW_HOME}/logs"
fi
export DEER_FLOW_OPS_LOG_LINES_MAX="${DEER_FLOW_OPS_LOG_LINES_MAX:-1000}"
export DEER_FLOW_OPS_LOG_TAIL_MAX_BYTES="${DEER_FLOW_OPS_LOG_TAIL_MAX_BYTES:-1048576}"
export DEER_FLOW_ADMIN_PORT="${DEER_FLOW_ADMIN_PORT:-8082}"
export DEER_FLOW_ADMIN_ENABLED="${DEER_FLOW_ADMIN_ENABLED:-false}"
export DEER_FLOW_ADMIN_ACTIONS_ENABLED="${DEER_FLOW_ADMIN_ACTIONS_ENABLED:-false}"
export DEER_FLOW_CHANNELS_LANGGRAPH_URL="${DEER_FLOW_CHANNELS_LANGGRAPH_URL:-http://127.0.0.1:8001/api}"
export DEER_FLOW_CHANNELS_GATEWAY_URL="${DEER_FLOW_CHANNELS_GATEWAY_URL:-http://127.0.0.1:8001}"
export DEER_FLOW_INTERNAL_GATEWAY_BASE_URL="${DEER_FLOW_INTERNAL_GATEWAY_BASE_URL:-http://127.0.0.1:8001}"
if [ -z "${GATEWAY_CORS_ORIGINS:-}" ] && [ -n "${SPACE_HOST:-}" ]; then
  export GATEWAY_CORS_ORIGINS="https://${SPACE_HOST}"
fi
export DEER_FLOW_TRUSTED_ORIGINS="${DEER_FLOW_TRUSTED_ORIGINS:-${GATEWAY_CORS_ORIGINS:-http://localhost:7860}}"
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export TAVILY_API_KEY="${TAVILY_API_KEY:-}"
export SERPER_API_KEY="${SERPER_API_KEY:-}"
export JINA_API_KEY="${JINA_API_KEY:-}"
export EXA_API_KEY="${EXA_API_KEY:-}"
export FIRECRAWL_API_KEY="${FIRECRAWL_API_KEY:-}"
export INFOQUEST_API_KEY="${INFOQUEST_API_KEY:-}"

mkdir -p \
  "${DEER_FLOW_HOME}/logs" \
  "${DEER_FLOW_DB_DIR}" \
  "${DEER_FLOW_OPS_LOG_DIR}" \
  "${DEER_FLOW_HOME}/run" \
  "${DEER_FLOW_HOME}/threads" \
  "${DEER_FLOW_HOME}/uploads" \
  "${DEER_FLOW_HOME}/tmp" \
  /tmp/nginx/client_body \
  /tmp/nginx/proxy \
  /tmp/nginx/fastcgi \
  /tmp/nginx/uwsgi \
  /tmp/nginx/scgi

if [ "${DEER_FLOW_MANAGED_CONFIG}" = "true" ]; then
  log "Syncing managed config at ${DEER_FLOW_CONFIG_PATH}"
  cp /home/user/app/hfs/config/config.hfs.yaml "${DEER_FLOW_CONFIG_PATH}"
elif [ ! -f "${DEER_FLOW_CONFIG_PATH}" ]; then
  log "Creating initial config at ${DEER_FLOW_CONFIG_PATH}"
  cp /home/user/app/hfs/config/config.hfs.yaml "${DEER_FLOW_CONFIG_PATH}"
fi

if [ ! -f "${DEER_FLOW_EXTENSIONS_CONFIG_PATH}" ]; then
  log "Creating initial extensions config at ${DEER_FLOW_EXTENSIONS_CONFIG_PATH}"
  cp /home/user/app/hfs/config/extensions_config.json "${DEER_FLOW_EXTENSIONS_CONFIG_PATH}"
fi

if ! printf 'ok\n' > "${DEER_FLOW_HOME}/.hfs-persistence-probe" 2>/dev/null; then
  log "WARN: failed to write persistence probe under ${DEER_FLOW_HOME}"
fi

# Generate stable secrets if the user did not provide them through HF Secrets.
# They remain stable only if DEER_FLOW_HOME persists. BETTER_AUTH_SECRET is a
# legacy wrapper input; current DeerFlow signs Gateway sessions with AUTH_JWT_SECRET.
if [ -z "${AUTH_JWT_SECRET:-}" ] && [ -n "${BETTER_AUTH_SECRET:-}" ]; then
  AUTH_JWT_SECRET="${BETTER_AUTH_SECRET}"
  export AUTH_JWT_SECRET
  log "Using legacy BETTER_AUTH_SECRET as the AUTH_JWT_SECRET compatibility source."
fi

if [ -z "${AUTH_JWT_SECRET:-}" ]; then
  secret_file="${DEER_FLOW_HOME}/.jwt_secret"
  if [ -f "${secret_file}" ]; then
    AUTH_JWT_SECRET="$(cat "${secret_file}")"
    export AUTH_JWT_SECRET
  else
    AUTH_JWT_SECRET="$(make_secret)"
    export AUTH_JWT_SECRET
    umask 077
    printf '%s' "${AUTH_JWT_SECRET}" > "${secret_file}"
    umask 022
  fi
fi

if [ -z "${DEER_FLOW_INTERNAL_AUTH_TOKEN:-}" ]; then
  token_file="${DEER_FLOW_HOME}/.internal-auth-token"
  if [ -f "${token_file}" ]; then
    DEER_FLOW_INTERNAL_AUTH_TOKEN="$(cat "${token_file}")"
    export DEER_FLOW_INTERNAL_AUTH_TOKEN
  else
    DEER_FLOW_INTERNAL_AUTH_TOKEN="$(make_secret)"
    export DEER_FLOW_INTERNAL_AUTH_TOKEN
    umask 077
    printf '%s' "${DEER_FLOW_INTERNAL_AUTH_TOKEN}" > "${token_file}"
    umask 022
  fi
fi

if [ -z "${OPENROUTER_API_KEY:-}" ] && [ -z "${OPENAI_API_KEY:-}" ]; then
  log "WARN: no OPENROUTER_API_KEY or OPENAI_API_KEY detected. Edit ${DEER_FLOW_CONFIG_PATH} or add a model API key in HF Secrets."
fi

log "DEER_FLOW_PROJECT_ROOT=${DEER_FLOW_PROJECT_ROOT}"
log "DEER_FLOW_HOME=${DEER_FLOW_HOME}"
log "DEER_FLOW_CONFIG_PATH=${DEER_FLOW_CONFIG_PATH}"
log "DEER_FLOW_EXTENSIONS_CONFIG_PATH=${DEER_FLOW_EXTENSIONS_CONFIG_PATH}"
log "DEER_FLOW_SKILLS_PATH=${DEER_FLOW_SKILLS_PATH}"
log "Starting supervisor"

exec /usr/bin/supervisord -c /home/user/app/hfs/supervisor/supervisord.conf
