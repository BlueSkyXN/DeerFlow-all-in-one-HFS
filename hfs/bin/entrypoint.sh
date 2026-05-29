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
export DEER_FLOW_CONFIG_PATH="${DEER_FLOW_CONFIG_PATH:-${DEER_FLOW_HOME}/config.yaml}"
export DEER_FLOW_EXTENSIONS_CONFIG_PATH="${DEER_FLOW_EXTENSIONS_CONFIG_PATH:-${DEER_FLOW_HOME}/extensions_config.json}"
export DEER_FLOW_SKILLS_PATH="${DEER_FLOW_SKILLS_PATH:-${DEER_FLOW_PROJECT_ROOT}/skills}"
export DEER_FLOW_MANAGED_CONFIG="${DEER_FLOW_MANAGED_CONFIG:-true}"
export GATEWAY_WORKERS="${GATEWAY_WORKERS:-1}"
export GATEWAY_ENABLE_DOCS="${GATEWAY_ENABLE_DOCS:-true}"
export DEER_FLOW_CHANNELS_LANGGRAPH_URL="${DEER_FLOW_CHANNELS_LANGGRAPH_URL:-http://127.0.0.1:8001/api}"
export DEER_FLOW_CHANNELS_GATEWAY_URL="${DEER_FLOW_CHANNELS_GATEWAY_URL:-http://127.0.0.1:8001}"
export DEER_FLOW_INTERNAL_GATEWAY_BASE_URL="${DEER_FLOW_INTERNAL_GATEWAY_BASE_URL:-http://127.0.0.1:8001}"
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
# They remain stable only if DEER_FLOW_HOME is persistent.
if [ -z "${BETTER_AUTH_SECRET:-}" ]; then
  secret_file="${DEER_FLOW_HOME}/.better-auth-secret"
  if [ -f "${secret_file}" ]; then
    BETTER_AUTH_SECRET="$(cat "${secret_file}")"
    export BETTER_AUTH_SECRET
  else
    BETTER_AUTH_SECRET="$(make_secret)"
    export BETTER_AUTH_SECRET
    umask 077
    printf '%s' "${BETTER_AUTH_SECRET}" > "${secret_file}"
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
