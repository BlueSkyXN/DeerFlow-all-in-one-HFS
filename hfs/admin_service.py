#!/usr/bin/env python3
"""Controlled admin service for DeerFlow-all-in-one-HFS."""

from __future__ import annotations

import hmac
import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

STARTED_AT = time.time()
ADMIN_PORT = int(os.environ.get("DEER_FLOW_ADMIN_PORT") or os.environ.get("ADMIN_PORT", "8082"))
SUPERVISOR_CONFIG = os.environ.get("DEER_FLOW_SUPERVISOR_CONFIG", "/home/user/app/hfs/supervisord.conf")
NGINX_CONFIG = os.environ.get("DEER_FLOW_NGINX_CONFIG", "/home/user/app/hfs/nginx.conf")
NGINX_BIN = os.environ.get("DEER_FLOW_NGINX_BIN", "/usr/sbin/nginx")
ALLOWED_RESTART_SERVICES = {"gateway", "frontend", "nginx"}

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
    "BETTER_AUTH_SECRET",
    "DEER_FLOW_INTERNAL_AUTH_TOKEN",
    "DEER_FLOW_ADMIN_TOKEN",
    "ADMIN_TOKEN",
    "DEER_FLOW_OPS_TOKEN",
    "OPS_TOKEN",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
]


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def parse_bool(value: str, default: bool = False) -> bool:
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def admin_enabled() -> bool:
    return parse_bool(env("DEER_FLOW_ADMIN_ENABLED") or env("ADMIN_ENABLED"), default=False)


def admin_actions_enabled() -> bool:
    return parse_bool(env("DEER_FLOW_ADMIN_ACTIONS_ENABLED") or env("ADMIN_ACTIONS_ENABLED"), default=False)


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
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
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
            processes.append({"name": parts[0], "state": parts[1], "detail": parts[2] if len(parts) > 2 else ""})
    result["processes"] = processes
    return result


def status_payload() -> dict[str, Any]:
    return {
        "status": "ok" if admin_enabled() and admin_token() else "locked",
        "admin_enabled": admin_enabled(),
        "actions_enabled": admin_actions_enabled(),
        "token_configured": bool(admin_token()),
        "uptime_seconds": round(time.time() - STARTED_AT, 1),
        "supervisor": supervisor_status() if admin_enabled() and admin_token() else {"processes": []},
    }


def config_payload() -> dict[str, Any]:
    return {
        "values": {key: env(key) for key in SAFE_CONFIG_KEYS if env(key)},
        "secret_presence": {key: bool(env(key)) for key in SECRET_KEYS},
    }


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
  <p>Token-protected control surface for this Hugging Face Space. Write actions are disabled unless DEER_FLOW_ADMIN_ACTIONS_ENABLED=true.</p>
  <section class="card">
    <h2>Token</h2>
    <div class="row"><input id="token" type="password" placeholder="DEER_FLOW_ADMIN_TOKEN" size="48" /><button onclick="saveToken()">Save token</button><button class="secondary" onclick="clearToken()">Clear</button></div>
  </section>
  <section class="card">
    <h2>Status</h2>
    <div class="row"><button onclick="loadStatus()">Refresh status</button><button class="secondary" onclick="loadConfig()">Config presence</button></div>
    <pre id="output">No request yet.</pre>
  </section>
  <section class="card">
    <h2>Fixed actions</h2>
    <div class="row"><button onclick="reloadNginx()">Reload nginx</button><select id="service"><option>gateway</option><option>frontend</option><option>nginx</option></select><button onclick="restartService()">Restart service</button></div>
  </section>
</main>
<script>
const output = document.getElementById('output');
const tokenInput = document.getElementById('token');
tokenInput.value = localStorage.getItem('deerflow_admin_token') || '';
function saveToken(){ localStorage.setItem('deerflow_admin_token', tokenInput.value); }
function clearToken(){ localStorage.removeItem('deerflow_admin_token'); tokenInput.value=''; }
function token(){ return tokenInput.value || localStorage.getItem('deerflow_admin_token') || ''; }
async function api(path, options={}){
  const headers = Object.assign({'Authorization': 'Bearer ' + token()}, options.headers || {});
  const res = await fetch(path, Object.assign({}, options, {headers}));
  const text = await res.text();
  let data; try { data = JSON.parse(text); } catch { data = text; }
  output.textContent = JSON.stringify({http_status: res.status, body: data}, null, 2);
}
function loadStatus(){ api('/_admin/api/status'); }
function loadConfig(){ api('/_admin/api/config'); }
function reloadNginx(){ api('/_admin/api/reload-nginx', {method:'POST'}); }
function restartService(){ api('/_admin/api/restart', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({service: document.getElementById('service').value})}); }
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
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
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
            self.send_json({"error": "admin_disabled", "message": "Set DEER_FLOW_ADMIN_ENABLED=true and DEER_FLOW_ADMIN_TOKEN to enable admin APIs."}, 403)
        elif not admin_token():
            self.send_json({"error": "admin_locked", "message": "DEER_FLOW_ADMIN_TOKEN is not configured."}, 403)
        else:
            self.send_json({"error": "unauthorized"}, 401)
        return False

    def require_actions(self) -> bool:
        if admin_actions_enabled():
            return True
        self.send_json({"error": "actions_disabled", "message": "Set DEER_FLOW_ADMIN_ACTIONS_ENABLED=true to allow fixed write actions."}, 403)
        return False

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
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
        self.send_json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if not self.require_admin() or not self.require_actions():
            return
        if path == "/api/reload-nginx":
            test_result = run_fixed([NGINX_BIN, "-t", "-c", NGINX_CONFIG], timeout=10)
            if not test_result.get("ok"):
                self.send_json({"action": "reload-nginx", "ok": False, "test": test_result}, 500)
                return
            reload_result = run_fixed([NGINX_BIN, "-s", "reload", "-c", NGINX_CONFIG], timeout=10)
            self.send_json({"action": "reload-nginx", "ok": bool(reload_result.get("ok")), "test": test_result, "reload": reload_result}, 200 if reload_result.get("ok") else 500)
            return
        if path == "/api/restart":
            service = str(self.read_json().get("service", ""))
            if service not in ALLOWED_RESTART_SERVICES:
                self.send_json({"error": "invalid_service", "allowed": sorted(ALLOWED_RESTART_SERVICES)}, 400)
                return
            result = run_fixed(["supervisorctl", "-c", SUPERVISOR_CONFIG, "restart", service], timeout=20)
            self.send_json({"action": "restart", "service": service, "ok": bool(result.get("ok")), "result": result}, 200 if result.get("ok") else 500)
            return
        self.send_json({"error": "not found"}, 404)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", ADMIN_PORT), AdminHandler)
    print(f"[admin-service] Listening on 127.0.0.1:{ADMIN_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
