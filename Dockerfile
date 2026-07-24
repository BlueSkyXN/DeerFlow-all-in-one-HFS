# syntax=docker/dockerfile:1.6

ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.7.20
FROM ${UV_IMAGE} AS uv-source

FROM python:3.12-slim-bookworm

ARG DEERFLOW_REPO=https://github.com/bytedance/deer-flow.git
ARG DEERFLOW_REF=964162747f4839a954e247bef82f5f69dde8219d
ARG NODE_MAJOR=22
ARG PNPM_VERSION=10.26.2
ARG APT_MIRROR=
ARG NPM_REGISTRY=
ARG UV_INDEX_URL=https://pypi.org/simple
ARG UV_EXTRAS=

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONIOENCODING=utf-8 \
    HOME=/home/user \
    PNPM_HOME=/home/user/.local/share/pnpm \
    PATH=/home/user/.local/share/pnpm:/home/user/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    DEER_FLOW_PROJECT_ROOT=/home/user/app/deer-flow \
    DEER_FLOW_HOME=/data/deer-flow \
    DEER_FLOW_DB_DIR=/data/deer-flow/data \
    DEER_FLOW_CONFIG_PATH=/data/deer-flow/config.yaml \
    DEER_FLOW_EXTENSIONS_CONFIG_PATH=/data/deer-flow/extensions_config.json \
    DEER_FLOW_SKILLS_PATH=/home/user/app/deer-flow/skills \
    GATEWAY_WORKERS=1 \
    GATEWAY_ENABLE_DOCS=true \
    DEER_FLOW_OPS_PORT=8081 \
    DEER_FLOW_OPS_SESSION_TTL_SECONDS=3600 \
    DEER_FLOW_OPS_COOKIE_SECURE=auto \
    DEER_FLOW_OPS_DEFAULT_CHECKS_ENABLED=true \
    DEER_FLOW_OPS_LOG_DIR=/data/deer-flow/logs \
    DEER_FLOW_OPS_LOG_LINES_MAX=1000 \
    DEER_FLOW_OPS_LOG_TAIL_MAX_BYTES=1048576 \
    DEER_FLOW_ADMIN_PORT=8082 \
    DEER_FLOW_ADMIN_ENABLED=false \
    DEER_FLOW_ADMIN_ACTIONS_ENABLED=false \
    CI=true

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN set -eux; \
    if [ -n "${APT_MIRROR}" ]; then \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources 2>/dev/null || true; \
      sed -i "s|deb.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list 2>/dev/null || true; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      bash \
      build-essential \
      ca-certificates \
      curl \
      git \
      gnupg \
      jq \
      nginx \
      passwd \
      procps \
      supervisor \
      tini; \
    mkdir -p /etc/apt/keyrings; \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
      | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg; \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_${NODE_MAJOR}.x nodistro main" \
      > /etc/apt/sources.list.d/nodesource.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends nodejs; \
    corepack enable; \
    if [ -n "${NPM_REGISTRY}" ]; then export COREPACK_NPM_REGISTRY="${NPM_REGISTRY}"; fi; \
    corepack install -g "pnpm@${PNPM_VERSION}" || npm install -g "pnpm@${PNPM_VERSION}"; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

COPY --from=uv-source /uv /uvx /usr/local/bin/

RUN set -eux; \
    if ! id -u user >/dev/null 2>&1; then \
      if getent passwd 1000 >/dev/null; then \
        existing_user="$(getent passwd 1000 | cut -d: -f1)"; \
        usermod -l user "${existing_user}" 2>/dev/null || true; \
        usermod -d /home/user -m user 2>/dev/null || true; \
      else \
        useradd -m -u 1000 user; \
      fi; \
    fi; \
    mkdir -p /home/user/app /data /tmp/nginx; \
    chown -R 1000:1000 /home/user /tmp/nginx; \
    chmod 777 /data /tmp/nginx

USER 1000
WORKDIR /home/user/app

RUN set -eux; \
    git init deer-flow; \
    cd deer-flow; \
    git remote add origin "${DEERFLOW_REPO}"; \
    git fetch --depth 1 origin "${DEERFLOW_REF}"; \
    git checkout --detach FETCH_HEAD; \
    git rev-parse HEAD > .deerflow-upstream-sha; \
    printf '%s\n' "${DEERFLOW_REF}" > .deerflow-upstream-ref; \
    python -c 'import pathlib, tomllib; root = pathlib.Path("."); data = tomllib.loads((root / "backend/pyproject.toml").read_text(encoding="utf-8")); (root / ".deerflow-upstream-version").write_text(str(data["project"]["version"]) + "\n", encoding="utf-8")'

RUN --mount=type=cache,target=/home/user/.cache/uv,uid=1000,gid=1000 \
    set -eux; \
    cd /home/user/app/deer-flow/backend; \
    if [ -n "${UV_EXTRAS}" ]; then \
      UV_INDEX_URL="${UV_INDEX_URL}" uv sync --extra "${UV_EXTRAS}"; \
    else \
      UV_INDEX_URL="${UV_INDEX_URL}" uv sync; \
    fi

RUN --mount=type=cache,target=/home/user/.local/share/pnpm/store,uid=1000,gid=1000 \
    set -eux; \
    if [ -n "${NPM_REGISTRY}" ]; then pnpm config set registry "${NPM_REGISTRY}"; fi; \
    pnpm config set store-dir /home/user/.local/share/pnpm/store; \
    cd /home/user/app/deer-flow/frontend; \
    pnpm install --frozen-lockfile

COPY --chown=1000:1000 hfs/config/next.hfs.config.js /home/user/app/next.hfs.config.js

RUN set -eux; \
    cd /home/user/app/deer-flow/frontend; \
    SKIP_ENV_VALIDATION=1 \
    NODE_OPTIONS=--max-old-space-size=3072 \
    pnpm typecheck

RUN set -eux; \
    cd /home/user/app/deer-flow/frontend; \
    mv next.config.js next.config.upstream.js; \
    cp /home/user/app/next.hfs.config.js next.config.js; \
    NEXT_TELEMETRY_DISABLED=1 \
    SKIP_ENV_VALIDATION=1 \
    DEER_FLOW_INTERNAL_GATEWAY_BASE_URL="${DEER_FLOW_INTERNAL_GATEWAY_BASE_URL:-http://127.0.0.1:8001}" \
    pnpm exec next build --webpack

COPY --chown=1000:1000 hfs /home/user/app/hfs
COPY --chown=1000:1000 docs /home/user/app/project-docs
COPY --chown=1000:1000 examples /home/user/app/project-examples
COPY --chown=1000:1000 scripts /home/user/app/project-scripts
COPY --chown=1000:1000 README.md /home/user/app/project-README.md

RUN set -eux; \
    chmod +x /home/user/app/hfs/bin/entrypoint.sh /home/user/app/hfs/bin/healthcheck.sh /home/user/app/project-scripts/smoke-test.sh; \
    mkdir -p /home/user/app/deer-flow/backend/.deer-flow

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
  CMD /home/user/app/hfs/bin/healthcheck.sh

ENTRYPOINT ["tini", "--", "/home/user/app/hfs/bin/entrypoint.sh"]
