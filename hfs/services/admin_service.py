#!/usr/bin/env python3
"""Controlled admin service for DeerFlow-all-in-one-HFS."""

from __future__ import annotations

import hmac
import json
import os
import re
import subprocess
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

STARTED_AT = time.time()
ADMIN_PORT = int(
    os.environ.get("DEER_FLOW_ADMIN_PORT") or os.environ.get("ADMIN_PORT", "8082")
)
SUPERVISOR_CONFIG = os.environ.get(
    "DEER_FLOW_SUPERVISOR_CONFIG", "/home/user/app/hfs/supervisor/supervisord.conf"
)
NGINX_CONFIG = os.environ.get(
    "DEER_FLOW_NGINX_CONFIG", "/home/user/app/hfs/nginx/nginx.conf"
)
NGINX_BIN = os.environ.get("DEER_FLOW_NGINX_BIN", "/usr/sbin/nginx")
ALLOWED_RESTART_SERVICES = {"gateway", "frontend", "nginx"}
ADMIN_INTENT_HEADER = "DeerFlow-HFS-Admin"
MAX_AUDIT_EVENTS = 500
MAX_AUDIT_BYTES = 1_048_576

SAFE_CONFIG_KEYS = [
    "DEER_FLOW_ENV",
    "SPACE_ID",
    "SPACE_HOST",
    "DEER_FLOW_HOME",
    "DEER_FLOW_CONFIG_PATH",
    "GATEWAY_WORKERS",
    "GATEWAY_ENABLE_DOCS",
    "DEER_FLOW_ADMIN_ENABLED",
    "DEER_FLOW_ADMIN_ACTIONS_ENABLED",
]

SECRET_KEYS = [
    "AUTH_JWT_SECRET",
    "BETTER_AUTH_SECRET",
    "DEER_FLOW_INTERNAL_AUTH_TOKEN",
    "DEER_FLOW_ADMIN_TOKEN",
    "ADMIN_TOKEN",
    "DEER_FLOW_OPS_TOKEN",
    "OPS_TOKEN",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
]

SECRET_NAME_PATTERN = re.compile(
    r"(?i)(authorization|api[_-]?key|secret|token|password)"
)


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


def admin_enabled() -> bool:
    return parse_bool(
        env("DEER_FLOW_ADMIN_ENABLED") or env("ADMIN_ENABLED"), default=False
    )


def admin_actions_enabled() -> bool:
    return parse_bool(
        env("DEER_FLOW_ADMIN_ACTIONS_ENABLED") or env("ADMIN_ACTIONS_ENABLED"),
        default=False,
    )


def admin_token() -> str:
    return env("DEER_FLOW_ADMIN_TOKEN") or env("ADMIN_TOKEN")


def supplied_token(handler: BaseHTTPRequestHandler) -> str:
    auth = handler.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return handler.headers.get("X-Admin-Token", "").strip()


def authorized(handler: BaseHTTPRequestHandler) -> bool:
    expected = admin_token()
    if not admin_enabled() or not expected:
        return False
    return hmac.compare_digest(supplied_token(handler), expected)


def run_fixed(command: list[str], timeout: int = 15) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout.strip()[-4000:],
            "stderr": result.stderr.strip()[-4000:],
            "ok": result.returncode == 0,
        }
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc), "ok": False}


def supervisor_status() -> dict[str, Any]:
    result = run_fixed(["supervisorctl", "-c", SUPERVISOR_CONFIG, "status"], timeout=8)
    processes = []
    for line in result.get("stdout", "").splitlines():
        parts = line.split(None, 2)
        if len(parts) >= 2:
            processes.append(
                {
                    "name": parts[0],
                    "state": parts[1],
                    "detail": parts[2] if len(parts) > 2 else "",
                }
            )
    result["processes"] = processes
    return result


def status_payload() -> dict[str, Any]:
    return {
        "status": "ok" if admin_enabled() and admin_token() else "locked",
        "admin_enabled": admin_enabled(),
        "actions_enabled": admin_actions_enabled(),
        "token_configured": bool(admin_token()),
        "uptime_seconds": round(time.time() - STARTED_AT, 1),
        "supervisor": supervisor_status()
        if admin_enabled() and admin_token()
        else {"processes": []},
    }


def config_payload() -> dict[str, Any]:
    return {
        "values": {key: env(key) for key in SAFE_CONFIG_KEYS if env(key)},
        "secret_presence": {key: bool(env(key)) for key in SECRET_KEYS},
    }


def redact_text(text: str) -> str:
    redacted = text
    for key in SECRET_KEYS:
        value = env(key)
        if len(value) >= 4:
            redacted = redacted.replace(value, f"[redacted:{key}]")
    redacted = re.sub(r"(?i)(\bbearer\s+)[^\s,;\"']+", r"\1[redacted]", redacted)
    redacted = re.sub(
        r"(?i)((?:[\"']?(?:authorization|api[_-]?key|secret|token|password)[\"']?)\s*[:=]\s*[\"']?)([^\s,;&\"']+)",
        r"\1[redacted]",
        redacted,
    )
    return redacted


def redact_payload(value: Any, key: str = "") -> Any:
    if key and SECRET_NAME_PATTERN.search(key):
        return "[redacted]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {
            item_key: redact_payload(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    return value


def actions_payload() -> dict[str, Any]:
    return {
        "status": "ok",
        "actions_enabled": admin_actions_enabled(),
        "read_only_actions": [
            {
                "name": "run-health-checks",
                "path": "/_admin/api/actions/run-health-checks",
                "method": "POST",
                "confirm": "run-health-checks",
            }
        ],
        "write_actions": [
            {
                "name": "reload-nginx",
                "path": "/_admin/api/reload-nginx",
                "method": "POST",
                "confirm": "reload-nginx",
                "enabled": admin_actions_enabled(),
            },
            {
                "name": "restart",
                "path": "/_admin/api/restart",
                "method": "POST",
                "confirm_pattern": "restart:<service>",
                "allowed_services": sorted(ALLOWED_RESTART_SERVICES),
                "enabled": admin_actions_enabled(),
            },
        ],
    }


def audit_log_path() -> Path:
    return (
        Path(env("DEER_FLOW_HOME", "/data/deer-flow")) / "logs" / "admin-actions.jsonl"
    )


def audit_payload(query: dict[str, list[str]]) -> dict[str, Any]:
    limit = parse_int(
        query.get("limit", ["100"])[0], 100, minimum=1, maximum=MAX_AUDIT_EVENTS
    )
    path = audit_log_path()
    if not path.exists():
        return {"status": "ok", "path": str(path), "events": []}
    events: list[Any] = []
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            handle.seek(max(size - MAX_AUDIT_BYTES, 0))
            raw = handle.read()
        lines = raw.decode("utf-8", errors="replace").splitlines()[-limit:]
    except OSError as exc:
        return {"status": "error", "error": str(exc), "events": []}
    for line in lines:
        try:
            events.append(redact_payload(json.loads(line)))
        except json.JSONDecodeError:
            events.append({"raw": redact_text(line[:1000])})
    return {
        "status": "ok",
        "path": str(path),
        "limit": limit,
        "tail_max_bytes": MAX_AUDIT_BYTES,
        "events": events,
    }


def health_checks_payload() -> dict[str, Any]:
    nginx_config = run_fixed([NGINX_BIN, "-t", "-c", NGINX_CONFIG], timeout=10)
    supervisor = supervisor_status()
    return {
        "status": "ok"
        if nginx_config.get("ok") and supervisor.get("ok")
        else "degraded",
        "nginx_config": nginx_config,
        "supervisor": supervisor,
    }


def audit_event(action: str, payload: dict[str, Any]) -> None:
    root = audit_log_path().parent
    try:
        root.mkdir(parents=True, exist_ok=True)
        event = {
            "ts": int(time.time()),
            "action": action,
            "payload": payload,
        }
        with audit_log_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        return


ADMIN_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DeerFlow Admin</title>
  <style>
    :root { color-scheme: light; font-family: ui-sans-serif, system-ui, sans-serif; background: #f5f7fb; color: #172033; }
    body { margin: 0; padding: 32px; }
    main { max-width: 1040px; margin: 0 auto; }
    .card { background: white; border: 1px solid #dde5f2; border-radius: 18px; padding: 20px; margin: 16px 0; box-shadow: 0 18px 45px rgba(23,32,51,.08); }
    input, button, select { font: inherit; padding: 10px 12px; border-radius: 10px; border: 1px solid #bdc8d8; }
    button { background: #173b57; color: white; cursor: pointer; border-color: #173b57; }
    button.secondary { background: #f5f7fb; color: #173b57; }
    pre { background: #0f1720; color: #d8f3dc; padding: 16px; border-radius: 14px; overflow: auto; }
    .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
  </style>
</head>
<body>
<main>
  <h1>DeerFlow Admin</h1>
  <p>Token-protected control surface for this Hugging Face Space. The public shell only stores a tab-local token and checks protected API status.</p>
  <section class="card">
    <h2>Token</h2>
    <p>The token is kept only in this browser tab and is not stored in browser storage.</p>
    <div class="row"><input id="token" type="password" autocomplete="off" placeholder="DEER_FLOW_ADMIN_TOKEN" size="48" /></div>
  </section>
  <section class="card">
    <h2>Status</h2>
    <div class="row"><button onclick="loadStatus()">Refresh status</button><button class="secondary" onclick="loadConfig()">Config presence</button><button class="secondary" onclick="loadActions()">Actions</button><button class="secondary" onclick="loadAudit()">Audit</button><button onclick="runHealthChecks()">Run health checks</button></div>
    <pre id="output">No request yet.</pre>
  </section>
</main>
<script>
const output = document.getElementById('output');
const tokenInput = document.getElementById('token');
function token(){ return tokenInput.value; }
async function api(path, options={}){
  const headers = Object.assign({'Authorization': 'Bearer ' + token(), 'X-DeerFlow-Admin-Intent': 'DeerFlow-HFS-Admin'}, options.headers || {});
  const res = await fetch(path, Object.assign({}, options, {headers}));
  const text = await res.text();
  let data; try { data = JSON.parse(text); } catch { data = text; }
  output.textContent = JSON.stringify({http_status: res.status, body: data}, null, 2);
}
function loadStatus(){ api('/_admin/api/status'); }
function loadConfig(){ api('/_admin/api/config'); }
function loadActions(){ api('/_admin/api/actions'); }
function loadAudit(){ api('/_admin/api/audit?limit=20'); }
function runHealthChecks(){ api('/_admin/api/actions/run-health-checks', {method: 'POST', headers: {'X-DeerFlow-Admin-Confirm': 'run-health-checks'}}); }
</script>
</body>
</html>
"""


class AdminHandler(BaseHTTPRequestHandler):
    server_version = "DeerFlowHFSAdmin/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[admin-service] {self.address_string()} {fmt % args}")

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
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            return {}
        if length <= 0:
            return {}
        raw = self.rfile.read(min(length, 65536))
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def require_admin(self) -> bool:
        if authorized(self):
            return True
        if not admin_enabled():
            self.send_json(
                {
                    "error": "admin_disabled",
                    "message": "Set DEER_FLOW_ADMIN_ENABLED=true and DEER_FLOW_ADMIN_TOKEN to enable admin APIs.",
                },
                403,
            )
        elif not admin_token():
            self.send_json(
                {
                    "error": "admin_locked",
                    "message": "DEER_FLOW_ADMIN_TOKEN is not configured.",
                },
                403,
            )
        else:
            self.send_json({"error": "unauthorized"}, 401)
        return False

    def require_actions(self) -> bool:
        if admin_actions_enabled():
            return True
        self.send_json(
            {
                "error": "actions_disabled",
                "message": "Set DEER_FLOW_ADMIN_ACTIONS_ENABLED=true to allow fixed write actions.",
            },
            403,
        )
        return False

    def require_post_guard(self, confirmation: str) -> bool:
        if self.headers.get("X-DeerFlow-Admin-Intent") != ADMIN_INTENT_HEADER:
            self.send_json(
                {
                    "error": "csrf_guard_required",
                    "message": "Missing admin intent header.",
                },
                403,
            )
            return False
        if self.headers.get("X-DeerFlow-Admin-Confirm") != confirmation:
            self.send_json(
                {"error": "confirmation_required", "expected": confirmation}, 409
            )
            return False
        return True

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = urllib.parse.parse_qs(parsed.query)
        if path == "/":
            self.send_html(ADMIN_HTML)
            return
        if path == "/api/status":
            if not self.require_admin():
                return
            self.send_json(status_payload())
            return
        if path == "/api/config":
            if not self.require_admin():
                return
            self.send_json(config_payload())
            return
        if path == "/api/actions":
            if not self.require_admin():
                return
            self.send_json(actions_payload())
            return
        if path == "/api/audit":
            if not self.require_admin():
                return
            data = audit_payload(query)
            self.send_json(data, 200 if data["status"] == "ok" else 500)
            return
        self.send_json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if not self.require_admin():
            return
        if path == "/api/actions/run-health-checks":
            if not self.require_post_guard("run-health-checks"):
                return
            data = health_checks_payload()
            audit_event(
                "run-health-checks",
                {
                    "status": data["status"],
                    "nginx_ok": bool(data["nginx_config"].get("ok")),
                    "supervisor_ok": bool(data["supervisor"].get("ok")),
                },
            )
            self.send_json(data, 200 if data["status"] == "ok" else 503)
            return
        if not self.require_actions():
            return
        if path == "/api/reload-nginx":
            if not self.require_post_guard("reload-nginx"):
                return
            test_result = run_fixed([NGINX_BIN, "-t", "-c", NGINX_CONFIG], timeout=10)
            if not test_result.get("ok"):
                self.send_json(
                    {"action": "reload-nginx", "ok": False, "test": test_result}, 500
                )
                return
            reload_result = run_fixed(
                [NGINX_BIN, "-s", "reload", "-c", NGINX_CONFIG], timeout=10
            )
            audit_event(
                "reload-nginx",
                {
                    "ok": bool(reload_result.get("ok")),
                    "returncode": reload_result.get("returncode"),
                },
            )
            self.send_json(
                {
                    "action": "reload-nginx",
                    "ok": bool(reload_result.get("ok")),
                    "test": test_result,
                    "reload": reload_result,
                },
                200 if reload_result.get("ok") else 500,
            )
            return
        if path == "/api/restart":
            service = str(self.read_json().get("service", ""))
            if service not in ALLOWED_RESTART_SERVICES:
                self.send_json(
                    {
                        "error": "invalid_service",
                        "allowed": sorted(ALLOWED_RESTART_SERVICES),
                    },
                    400,
                )
                return
            if not self.require_post_guard(f"restart:{service}"):
                return
            result = run_fixed(
                ["supervisorctl", "-c", SUPERVISOR_CONFIG, "restart", service],
                timeout=20,
            )
            audit_event(
                "restart",
                {
                    "service": service,
                    "ok": bool(result.get("ok")),
                    "returncode": result.get("returncode"),
                },
            )
            self.send_json(
                {
                    "action": "restart",
                    "service": service,
                    "ok": bool(result.get("ok")),
                    "result": result,
                },
                200 if result.get("ok") else 500,
            )
            return
        self.send_json({"error": "not found"}, 404)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", ADMIN_PORT), AdminHandler)
    print(f"[admin-service] Listening on 127.0.0.1:{ADMIN_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
