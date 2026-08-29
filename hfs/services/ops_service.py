#!/usr/bin/env python3
"""Read-only operations service for DeerFlow-all-in-one-HFS."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

STARTED_AT = time.time()
SERVICE_NAME = "DeerFlow-all-in-one-HFS"
OPS_PORT = int(
    os.environ.get("DEER_FLOW_OPS_PORT") or os.environ.get("OPS_PORT", "8081")
)
OPS_SESSION_COOKIE = "deerflow_ops_session"
SUPERVISOR_CONFIG = os.environ.get(
    "DEER_FLOW_SUPERVISOR_CONFIG", "/home/user/app/hfs/supervisor/supervisord.conf"
)
GATEWAY_HEALTH_URL = os.environ.get(
    "DEER_FLOW_GATEWAY_HEALTH_URL", "http://127.0.0.1:8001/health"
)
FRONTEND_URL = os.environ.get("DEER_FLOW_FRONTEND_URL", "http://127.0.0.1:3000/")
LOG_DIR = Path(
    os.environ.get("DEER_FLOW_OPS_LOG_DIR")
    or Path(os.environ.get("DEER_FLOW_HOME", "/data/deer-flow")) / "logs"
)

DEFAULT_SERVICE_LOGS = {
    "supervisord": "/tmp/supervisord.log",
    "admin-actions": "admin-actions.jsonl",
}

ERROR_PATTERNS = [
    "Traceback",
    "ERROR",
    "Error",
    "[error]",
    "FATAL",
    "CRITICAL",
    "Permission denied",
    "Connection refused",
    "failed",
    "exited:",
]

IGNORED_ERROR_PATTERNS = [
    "GET /_ops/errors",
]

SAFE_CONFIG_KEYS = [
    "DEER_FLOW_ENV",
    "SPACE_ID",
    "SPACE_HOST",
    "DEER_FLOW_PROJECT_ROOT",
    "DEER_FLOW_HOME",
    "DEER_FLOW_DB_DIR",
    "DEER_FLOW_CONFIG_PATH",
    "DEER_FLOW_EXTENSIONS_CONFIG_PATH",
    "DEER_FLOW_SKILLS_PATH",
    "GATEWAY_WORKERS",
    "GATEWAY_ENABLE_DOCS",
    "GATEWAY_CORS_ORIGINS",
    "DEER_FLOW_TRUSTED_ORIGINS",
    "DEER_FLOW_OPS_PORT",
    "DEER_FLOW_OPS_SESSION_TTL_SECONDS",
    "DEER_FLOW_OPS_COOKIE_SECURE",
    "DEER_FLOW_OPS_DEFAULT_CHECKS_ENABLED",
    "DEER_FLOW_OPS_LOG_DIR",
    "DEER_FLOW_OPS_LOG_LINES_MAX",
    "DEER_FLOW_OPS_LOG_TAIL_MAX_BYTES",
    "DEER_FLOW_ADMIN_PORT",
    "DEER_FLOW_ADMIN_ENABLED",
    "DEER_FLOW_ADMIN_ACTIONS_ENABLED",
    "HF_HOME",
]

SECRET_KEYS = [
    "AUTH_JWT_SECRET",
    "DATABASE_URL",
    "GITHUB_TOKEN",
    "HF_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
    "LANGFUSE_SECRET_KEY",
    "LANGSMITH_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "VOLCENGINE_API_KEY",
    "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY",
    "MINIMAX_API_KEY",
    "STEPFUN_API_KEY",
    "MIMO_API_KEY",
    "BRAVE_SEARCH_API_KEY",
    "BROWSERLESS_TOKEN",
    "E2B_API_KEY",
    "PROVISIONER_API_KEY",
    "TAVILY_API_KEY",
    "SERPER_API_KEY",
    "JINA_API_KEY",
    "EXA_API_KEY",
    "FIRECRAWL_API_KEY",
    "INFOQUEST_API_KEY",
    "BETTER_AUTH_SECRET",
    "DEER_FLOW_INTERNAL_AUTH_TOKEN",
    "OPS_TOKEN",
    "ADMIN_PASSWORD",
]


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def parse_bool(value: str, default: bool = False) -> bool:
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_int(
    value: Any, default: int, minimum: int | None = None, maximum: int | None = None
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def parse_float(
    value: Any,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def ops_token() -> str:
    return env("OPS_TOKEN")


def ops_session_ttl_seconds() -> int:
    return parse_int(
        env("DEER_FLOW_OPS_SESSION_TTL_SECONDS") or env("OPS_SESSION_TTL_SECONDS"),
        3600,
        minimum=60,
        maximum=86400,
    )


def log_lines_max() -> int:
    return parse_int(
        env("DEER_FLOW_OPS_LOG_LINES_MAX") or env("OPS_LOG_LINES_MAX"),
        1000,
        minimum=1,
        maximum=10000,
    )


def log_tail_max_bytes() -> int:
    return parse_int(
        env("DEER_FLOW_OPS_LOG_TAIL_MAX_BYTES") or env("OPS_LOG_TAIL_MAX_BYTES"),
        1_048_576,
        minimum=1,
        maximum=100 * 1024 * 1024,
    )


def sign_ops_message(*parts: str) -> str:
    token = ops_token()
    payload = "|".join(parts).encode("utf-8")
    return hmac.new(token.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def make_ops_session() -> tuple[str, int]:
    expires_at = int(time.time()) + ops_session_ttl_seconds()
    nonce = hashlib.sha256(
        f"{time.time()}:{os.urandom(16).hex()}".encode("utf-8")
    ).hexdigest()[:32]
    signature = sign_ops_message("ops-session", str(expires_at), nonce)
    return f"{expires_at}.{nonce}.{signature}", expires_at


def parse_ops_session(cookie_value: str) -> bool:
    try:
        expires_raw, nonce, signature = cookie_value.split(".", 2)
        expires_at = int(expires_raw)
    except (AttributeError, ValueError):
        return False
    if expires_at < int(time.time()) or not nonce or not signature:
        return False
    expected = sign_ops_message("ops-session", str(expires_at), nonce)
    return hmac.compare_digest(signature, expected)


def supplied_header_token(handler: BaseHTTPRequestHandler) -> str:
    ops_header = handler.headers.get("X-Ops-Token", "").strip()
    if ops_header:
        return ops_header
    auth = handler.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return ""


def cookie_authorized(handler: BaseHTTPRequestHandler) -> bool:
    raw = handler.headers.get("Cookie", "")
    if not raw:
        return False
    cookie = SimpleCookie()
    try:
        cookie.load(raw)
    except Exception:
        return False
    morsel = cookie.get(OPS_SESSION_COOKIE)
    return bool(morsel and parse_ops_session(morsel.value))


def auth_source(handler: BaseHTTPRequestHandler) -> str:
    expected = ops_token()
    if not expected:
        return ""
    header_token = supplied_header_token(handler)
    if header_token and hmac.compare_digest(header_token, expected):
        return "header"
    if cookie_authorized(handler):
        return "cookie"
    return ""


def http_check(name: str, url: str, timeout: float = 3.0) -> dict[str, Any]:
    started = time.time()
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "deerflow-hfs-ops/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = int(resp.getcode())
        return {
            "name": name,
            "status": "ok" if 200 <= code < 400 else "error",
            "http_code": code,
            "latency_ms": round((time.time() - started) * 1000, 1),
        }
    except urllib.error.HTTPError as exc:
        return {
            "name": name,
            "status": "error",
            "http_code": exc.code,
            "error": str(exc),
        }
    except Exception as exc:
        return {"name": name, "status": "error", "error": str(exc)}


def tcp_check(name: str, host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    started = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {
                "name": name,
                "status": "ok",
                "latency_ms": round((time.time() - started) * 1000, 1),
            }
    except Exception as exc:
        return {"name": name, "status": "error", "error": str(exc)}


def file_check(name: str, path: str) -> dict[str, Any]:
    target = Path(path)
    return {
        "name": name,
        "status": "ok" if target.exists() else "error",
        "path": str(target),
    }


def upstream_sha() -> str:
    return upstream_metadata("sha")


def upstream_metadata(name: str) -> str:
    target = (
        Path(env("DEER_FLOW_PROJECT_ROOT", "/home/user/app/deer-flow"))
        / f".deerflow-upstream-{name}"
    )
    try:
        return target.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def readiness(include_details: bool = True) -> dict[str, Any]:
    deer_flow_home = env("DEER_FLOW_HOME", "/data/deer-flow")
    database_dir = Path(env("DEER_FLOW_DB_DIR", str(Path(deer_flow_home) / "data")))
    checks = [tcp_check("ops_port", "127.0.0.1", OPS_PORT)]
    if parse_bool(
        env("DEER_FLOW_OPS_DEFAULT_CHECKS_ENABLED")
        or env("OPS_DEFAULT_CHECKS_ENABLED", "true"),
        default=True,
    ):
        checks.extend(
            [
                http_check("gateway_health", GATEWAY_HEALTH_URL),
                http_check("frontend_http", FRONTEND_URL),
                file_check(
                    "persistence_probe",
                    str(Path(deer_flow_home) / ".hfs-persistence-probe"),
                ),
                file_check("database_dir", str(database_dir)),
                file_check("database", str(database_dir / "deerflow.db")),
                file_check(
                    "config",
                    env("DEER_FLOW_CONFIG_PATH", "/data/deer-flow/config.yaml"),
                ),
                file_check(
                    "extensions_config",
                    env(
                        "DEER_FLOW_EXTENSIONS_CONFIG_PATH",
                        "/data/deer-flow/extensions_config.json",
                    ),
                ),
            ]
        )
    ok = all(item.get("status") == "ok" for item in checks)
    return {
        "status": "ok" if ok else "degraded",
        "service": SERVICE_NAME,
        "uptime_seconds": round(time.time() - STARTED_AT, 1),
        **({"upstream_sha": upstream_sha()} if include_details else {}),
        "checks": checks
        if include_details
        else [
            {"name": item.get("name"), "status": item.get("status")} for item in checks
        ],
    }


def supervisor_status() -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["supervisorctl", "-c", SUPERVISOR_CONFIG, "status"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    processes = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) >= 2:
            processes.append(
                {
                    "name": parts[0],
                    "state": parts[1],
                    "detail": parts[2] if len(parts) > 2 else "",
                }
            )
    return {
        "status": "ok" if result.returncode == 0 else "error",
        "returncode": result.returncode,
        "processes": processes,
        "stderr": result.stderr.strip()[:2000],
    }


def safe_config() -> dict[str, Any]:
    return {
        "values": {key: env(key) for key in SAFE_CONFIG_KEYS if env(key) != ""},
        "secret_presence": {key: bool(env(key)) for key in SECRET_KEYS},
        "ops_locked": not bool(ops_token()),
    }


def disk_usage_payload(path: Path) -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        return {"path": str(path), "status": "error", "error": str(exc)}
    return {
        "path": str(path),
        "status": "ok",
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


def memory_payload() -> dict[str, Any]:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return {"status": "unavailable"}
    values: dict[str, int] = {}
    try:
        for line in meminfo.read_text(encoding="utf-8", errors="replace").splitlines():
            key, _, rest = line.partition(":")
            parts = rest.strip().split()
            if parts:
                values[key] = int(parts[0]) * 1024
    except OSError as exc:
        return {"status": "error", "error": str(exc)}
    return {
        "status": "ok",
        "total_bytes": values.get("MemTotal"),
        "available_bytes": values.get("MemAvailable"),
    }


def system_payload() -> dict[str, Any]:
    home = Path(env("DEER_FLOW_HOME", "/data/deer-flow"))
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "hostname": socket.gethostname(),
        "memory": memory_payload(),
        "disk": disk_usage_payload(home if home.exists() else Path("/tmp")),
    }


def version_payload() -> dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "component": "ops",
        "upstream_sha": upstream_sha(),
        "upstream_ref": upstream_metadata("ref"),
        "upstream_version": upstream_metadata("version"),
        "space_id": env("SPACE_ID"),
        "space_host": env("SPACE_HOST"),
        "started_at": STARTED_AT,
        "uptime_seconds": round(time.time() - STARTED_AT, 1),
    }


def persistence_payload() -> dict[str, Any]:
    home = Path(env("DEER_FLOW_HOME", "/data/deer-flow"))
    database_dir = Path(env("DEER_FLOW_DB_DIR", str(home / "data")))
    required_checks = [
        file_check("home", str(home)),
        file_check("database_dir", str(database_dir)),
        file_check("database", str(database_dir / "deerflow.db")),
        file_check("persistence_probe", str(home / ".hfs-persistence-probe")),
    ]
    observed_paths = [
        file_check("logs", str(home / "logs")),
        file_check("run", str(home / "run")),
        file_check("users", str(home / "users")),
        file_check("legacy_threads", str(home / "threads")),
        file_check("legacy_uploads", str(home / "uploads")),
    ]
    writable = False
    try:
        probe = home / ".hfs-ops-write-check"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
        writable = True
    except OSError:
        writable = False
    ok = writable and all(item.get("status") == "ok" for item in required_checks)
    return {
        "status": "ok" if ok else "degraded",
        "home": str(home),
        "database_dir": str(database_dir),
        "writable": writable,
        "checks": required_checks,
        "observed_paths": observed_paths,
    }


def metrics_payload() -> str:
    data = readiness(include_details=False)
    status_value = 1 if data["status"] == "ok" else 0
    lines = [
        "# HELP deerflow_hfs_ops_ready Ops readiness status, 1 for ok and 0 for degraded.",
        "# TYPE deerflow_hfs_ops_ready gauge",
        f"deerflow_hfs_ops_ready {status_value}",
        "# HELP deerflow_hfs_ops_uptime_seconds Ops service uptime in seconds.",
        "# TYPE deerflow_hfs_ops_uptime_seconds gauge",
        f"deerflow_hfs_ops_uptime_seconds {round(time.time() - STARTED_AT, 1)}",
    ]
    for check in data.get("checks", []):
        name = re.sub(r"[^a-zA-Z0-9_]", "_", str(check.get("name", "unknown")))
        value = 1 if check.get("status") == "ok" else 0
        lines.append(f'deerflow_hfs_ops_check_ok{{check="{name}"}} {value}')
    return "\n".join(lines) + "\n"


def safe_log_filename(filename: Any) -> str | None:
    if not isinstance(filename, str) or not filename:
        return None
    path = Path(filename)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return str(path)


def load_service_logs() -> dict[str, str]:
    service_logs = dict(DEFAULT_SERVICE_LOGS)
    raw = env("DEER_FLOW_OPS_LOG_SERVICES_JSON") or env("OPS_LOG_SERVICES_JSON")
    if not raw:
        return service_logs
    try:
        configured = json.loads(raw)
    except json.JSONDecodeError:
        return service_logs
    if not isinstance(configured, dict):
        return service_logs
    for service, filename in configured.items():
        if not isinstance(service, str) or not service:
            continue
        safe_filename = safe_log_filename(filename)
        if safe_filename:
            service_logs[service] = safe_filename
    return service_logs


SERVICE_LOGS = load_service_logs()


def resolve_log_path(filename: str) -> Path | None:
    if filename.startswith("/"):
        fixed = Path(filename).resolve(strict=False)
        if filename in DEFAULT_SERVICE_LOGS.values():
            return fixed
        return None
    root = LOG_DIR.resolve(strict=False)
    target = (root / filename).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def secret_values() -> list[tuple[str, str]]:
    values = []
    for key in SECRET_KEYS:
        value = env(key)
        if len(value) >= 4:
            values.append((key, value))
    return sorted(values, key=lambda item: len(item[1]), reverse=True)


def redact_text(text: str) -> str:
    redacted = text
    for key, value in secret_values():
        redacted = redacted.replace(value, f"[redacted:{key}]")
    redacted = re.sub(r"(?i)(\bbearer\s+)[^\s,;\"']+", r"\1[redacted]", redacted)
    redacted = re.sub(
        r"(?i)\b([a-z][a-z0-9+.-]*://[^:/\s]+:)[^@\s]+@", r"\1[redacted]@", redacted
    )
    redacted = re.sub(
        r"(?i)((?:[\"']?(?:authorization|api[_-]?key|secret|token|password)[\"']?)\s*[:=]\s*[\"']?)([^\s,;&\"']+)",
        r"\1[redacted]",
        redacted,
    )
    return redacted


def tail_file(path: Path, lines: int) -> str:
    if not path.exists():
        return ""
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            handle.seek(max(size - log_tail_max_bytes(), 0))
            data = handle.read()
    except OSError as exc:
        return f"unable to read log: {exc}"
    return redact_text(
        b"\n".join(data.splitlines()[-lines:]).decode("utf-8", errors="replace")
    )


def logs_payload(query: dict[str, list[str]]) -> dict[str, Any]:
    service = query.get("service", ["supervisord"])[0]
    requested_lines = parse_int(
        query.get("lines", ["200"])[0], 200, minimum=1, maximum=log_lines_max()
    )
    filename = SERVICE_LOGS.get(service)
    if not filename:
        return {
            "status": "error",
            "error": "unknown service",
            "allowed_services": sorted(SERVICE_LOGS),
        }
    path = resolve_log_path(filename)
    if path is None:
        return {"status": "error", "error": "log path is not allowed"}
    return {
        "status": "ok" if path.exists() else "missing",
        "service": service,
        "path": str(path),
        "lines": requested_lines,
        "content": tail_file(path, requested_lines),
    }


def matched_error_pattern(line: str) -> str | None:
    if any(pattern in line for pattern in IGNORED_ERROR_PATTERNS):
        return None
    for pattern in ERROR_PATTERNS:
        if pattern in line:
            return pattern
    return None


def errors_payload(query: dict[str, list[str]]) -> dict[str, Any]:
    requested_lines = parse_int(
        query.get("lines", ["300"])[0], 300, minimum=1, maximum=log_lines_max()
    )
    match_limit = parse_int(query.get("limit", ["200"])[0], 200, minimum=1, maximum=500)
    matches: deque[dict[str, Any]] = deque(maxlen=match_limit)
    groups: dict[str, dict[str, Any]] = {}
    total_matches = 0
    for service, filename in SERVICE_LOGS.items():
        path = resolve_log_path(filename)
        if path is None or not path.exists():
            continue
        for line in tail_file(path, requested_lines).splitlines():
            pattern = matched_error_pattern(line)
            if not pattern:
                continue
            total_matches += 1
            entry = {"service": service, "pattern": pattern, "line": line[:1000]}
            matches.append(entry)
            group = groups.setdefault(
                service,
                {
                    "service": service,
                    "count": 0,
                    "pattern_counts": {},
                    "matches": deque(maxlen=match_limit),
                },
            )
            group["count"] += 1
            group["pattern_counts"][pattern] = (
                group["pattern_counts"].get(pattern, 0) + 1
            )
            group["matches"].append({"pattern": pattern, "line": line[:1000]})
    return {
        "status": "ok" if total_matches == 0 else "degraded",
        "line_limit": requested_lines,
        "match_limit": match_limit,
        "count": total_matches,
        "matches": list(matches),
        "groups": [
            {**group, "matches": list(group["matches"])}
            for group in sorted(groups.values(), key=lambda item: item["service"])
        ],
    }


OPS_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DeerFlow Ops</title>
  <style>
    :root { color-scheme: light; font-family: ui-sans-serif, system-ui, sans-serif; background: #f6f8fb; color: #172033; }
    body { margin: 0; padding: 28px; }
    main { max-width: 1040px; margin: 0 auto; }
    .panel { background: #fff; border: 1px solid #dbe4f0; border-radius: 10px; padding: 18px; margin: 14px 0; }
    input, button, select { font: inherit; padding: 9px 11px; border-radius: 8px; border: 1px solid #b8c4d6; }
    button { background: #17415f; border-color: #17415f; color: #fff; cursor: pointer; }
    button.secondary { background: #f6f8fb; color: #17415f; }
    pre { background: #101820; color: #d7f7df; padding: 14px; border-radius: 8px; overflow: auto; min-height: 180px; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
  </style>
</head>
<body>
<main>
  <h1>DeerFlow Ops</h1>
  <section class="panel">
    <div class="row">
      <input id="token" type="password" autocomplete="off" placeholder="OPS_TOKEN" size="42" />
      <button onclick="api('/_ops/status')">Status</button>
      <button onclick="api('/_ops/health')">Health</button>
      <button onclick="api('/_ops/system')">System</button>
      <button onclick="api('/_ops/persistence')">Persistence</button>
      <button onclick="api('/_ops/config')">Config</button>
      <button onclick="api('/_ops/errors')">Errors</button>
      <button class="secondary" onclick="api('/_ops/logs?service=supervisord&lines=120')">Logs</button>
    </div>
  </section>
  <pre id="output">Public probes: /_ops/healthz and /_ops/readyz</pre>
</main>
<script>
const output = document.getElementById('output');
const tokenInput = document.getElementById('token');
async function api(path) {
  const headers = {};
  if (tokenInput.value) headers['Authorization'] = 'Bearer ' + tokenInput.value;
  const res = await fetch(path, {headers});
  const text = await res.text();
  let body; try { body = JSON.parse(text); } catch { body = text; }
  output.textContent = JSON.stringify({http_status: res.status, body}, null, 2);
}
</script>
</body>
</html>
"""


class OpsHandler(BaseHTTPRequestHandler):
    server_version = "DeerFlowHFSOps/1.0"

    def setup(self) -> None:
        super().setup()
        timeout = parse_float(
            env("DEER_FLOW_OPS_HTTP_TIMEOUT_SECONDS")
            or env("OPS_HTTP_TIMEOUT_SECONDS"),
            30.0,
            minimum=1.0,
            maximum=600.0,
        )
        self.request.settimeout(timeout)
        self.ops_auth_source = ""

    def log_message(self, fmt: str, *args: Any) -> None:
        sanitized_path = urllib.parse.urlparse(self.path).path
        print(
            f"[ops-service] {self.address_string()} {(fmt % args).replace(self.path, sanitized_path)}"
        )

    def cookie_secure_enabled(self) -> bool:
        mode = (
            (env("DEER_FLOW_OPS_COOKIE_SECURE") or env("OPS_COOKIE_SECURE", "auto"))
            .strip()
            .lower()
        )
        if mode in {"1", "true", "yes", "on"}:
            return True
        if mode in {"0", "false", "no", "off"}:
            return False
        proto = (
            self.headers.get("X-Forwarded-Proto", "").split(",", 1)[0].strip().lower()
        )
        return proto == "https"

    def session_cookie_header(self) -> str:
        value, expires_at = make_ops_session()
        max_age = max(expires_at - int(time.time()), 0)
        secure = "; Secure" if self.cookie_secure_enabled() else ""
        return f"{OPS_SESSION_COOKIE}={value}; Path=/_ops/; Max-Age={max_age}; HttpOnly; SameSite=Strict{secure}"

    def maybe_send_session_cookie(self) -> None:
        if self.ops_auth_source == "header":
            self.send_header("Set-Cookie", self.session_cookie_header())

    def send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
        self.send_header("Content-Length", str(len(body)))
        self.maybe_send_session_cookie()
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        self.send_header("Content-Length", str(len(body)))
        self.maybe_send_session_cookie()
        self.end_headers()
        self.wfile.write(body)

    def send_text(
        self,
        body: str,
        status: int = 200,
        content_type: str = "text/plain; charset=utf-8",
    ) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", str(len(data)))
        self.maybe_send_session_cookie()
        self.end_headers()
        self.wfile.write(data)

    def require_auth(self) -> bool:
        self.ops_auth_source = auth_source(self)
        if self.ops_auth_source:
            return True
        self.send_json(
            {
                "error": "unauthorized",
                "message": "Set OPS_TOKEN and pass X-Ops-Token or Authorization: Bearer <token>.",
            },
            401,
        )
        return False

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = urllib.parse.parse_qs(parsed.query)
        if path == "/":
            self.send_html(OPS_HTML)
            return
        if path == "/healthz":
            self.send_json(
                {
                    "status": "ok",
                    "service": SERVICE_NAME,
                    "component": "ops",
                    "uptime_seconds": round(time.time() - STARTED_AT, 1),
                }
            )
            return
        if path == "/readyz":
            data = readiness(include_details=False)
            self.send_json(data, 200 if data["status"] == "ok" else 503)
            return
        if not self.require_auth():
            return
        if path == "/health":
            data = readiness(include_details=True)
            self.send_json(data, 200 if data["status"] == "ok" else 503)
        elif path == "/status":
            self.send_json(
                {"readiness": readiness(), "supervisor": supervisor_status()}
            )
        elif path == "/config":
            self.send_json(safe_config())
        elif path == "/system":
            self.send_json({"status": "ok", "system": system_payload()})
        elif path == "/persistence":
            data = persistence_payload()
            self.send_json(data, 200 if data["status"] == "ok" else 503)
        elif path == "/version":
            self.send_json({"status": "ok", "version": version_payload()})
        elif path == "/metrics":
            self.send_text(
                metrics_payload(),
                content_type="text/plain; version=0.0.4; charset=utf-8",
            )
        elif path == "/logs":
            data = logs_payload(query)
            self.send_json(data, 200 if data["status"] == "ok" else 404)
        elif path == "/errors":
            self.send_json(errors_payload(query))
        else:
            self.send_json({"error": "not found"}, 404)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", OPS_PORT), OpsHandler)
    print(f"[ops-service] Listening on 127.0.0.1:{OPS_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
