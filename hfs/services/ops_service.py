#!/usr/bin/env python3
"""Read-only operations service for DeerFlow-all-in-one-HFS."""

from __future__ import annotations

import hmac
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

STARTED_AT = time.time()
SERVICE_NAME = "DeerFlow-all-in-one-HFS"
OPS_PORT = int(os.environ.get("DEER_FLOW_OPS_PORT") or os.environ.get("OPS_PORT", "8081"))
SUPERVISOR_CONFIG = os.environ.get("DEER_FLOW_SUPERVISOR_CONFIG", "/home/user/app/hfs/supervisor/supervisord.conf")
GATEWAY_HEALTH_URL = os.environ.get("DEER_FLOW_GATEWAY_HEALTH_URL", "http://127.0.0.1:8001/health")
FRONTEND_URL = os.environ.get("DEER_FLOW_FRONTEND_URL", "http://127.0.0.1:3000/")

SAFE_CONFIG_KEYS = [
    "DEER_FLOW_ENV",
    "SPACE_ID",
    "SPACE_HOST",
    "DEER_FLOW_PROJECT_ROOT",
    "DEER_FLOW_HOME",
    "DEER_FLOW_CONFIG_PATH",
    "DEER_FLOW_EXTENSIONS_CONFIG_PATH",
    "DEER_FLOW_SKILLS_PATH",
    "GATEWAY_WORKERS",
    "GATEWAY_ENABLE_DOCS",
    "DEER_FLOW_OPS_PORT",
    "DEER_FLOW_ADMIN_PORT",
    "DEER_FLOW_ADMIN_ENABLED",
    "DEER_FLOW_ADMIN_ACTIONS_ENABLED",
    "HF_HOME",
]

SECRET_KEYS = [
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "TAVILY_API_KEY",
    "SERPER_API_KEY",
    "JINA_API_KEY",
    "EXA_API_KEY",
    "FIRECRAWL_API_KEY",
    "INFOQUEST_API_KEY",
    "BETTER_AUTH_SECRET",
    "DEER_FLOW_INTERNAL_AUTH_TOKEN",
    "DEER_FLOW_OPS_TOKEN",
    "OPS_TOKEN",
    "DEER_FLOW_ADMIN_TOKEN",
    "ADMIN_TOKEN",
]


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def parse_bool(value: str, default: bool = False) -> bool:
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def ops_token() -> str:
    return env("DEER_FLOW_OPS_TOKEN") or env("OPS_TOKEN")


def supplied_token(handler: BaseHTTPRequestHandler) -> str:
    auth = handler.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return handler.headers.get("X-Ops-Token", "").strip()


def authorized(handler: BaseHTTPRequestHandler) -> bool:
    expected = ops_token()
    if not expected:
        return False
    return hmac.compare_digest(supplied_token(handler), expected)


def http_check(name: str, url: str, timeout: float = 3.0) -> dict[str, Any]:
    started = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "deerflow-hfs-ops/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = int(resp.getcode())
        return {"name": name, "status": "ok" if 200 <= code < 400 else "error", "http_code": code, "latency_ms": round((time.time() - started) * 1000, 1)}
    except urllib.error.HTTPError as exc:
        return {"name": name, "status": "error", "http_code": exc.code, "error": str(exc)}
    except Exception as exc:
        return {"name": name, "status": "error", "error": str(exc)}


def tcp_check(name: str, host: str, port: int, timeout: float = 2.0) -> dict[str, Any]:
    started = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"name": name, "status": "ok", "latency_ms": round((time.time() - started) * 1000, 1)}
    except Exception as exc:
        return {"name": name, "status": "error", "error": str(exc)}


def file_check(name: str, path: str) -> dict[str, Any]:
    target = Path(path)
    return {"name": name, "status": "ok" if target.exists() else "error", "path": str(target)}


def upstream_sha() -> str:
    target = Path(env("DEER_FLOW_PROJECT_ROOT", "/home/user/app/deer-flow")) / ".deerflow-upstream-sha"
    try:
        return target.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def readiness() -> dict[str, Any]:
    deer_flow_home = env("DEER_FLOW_HOME", "/data/deer-flow")
    checks = [
        http_check("gateway_health", GATEWAY_HEALTH_URL),
        http_check("frontend_http", FRONTEND_URL),
        tcp_check("ops_port", "127.0.0.1", OPS_PORT),
        file_check("persistence_probe", str(Path(deer_flow_home) / ".hfs-persistence-probe")),
        file_check("config", env("DEER_FLOW_CONFIG_PATH", "/data/deer-flow/config.yaml")),
        file_check("extensions_config", env("DEER_FLOW_EXTENSIONS_CONFIG_PATH", "/data/deer-flow/extensions_config.json")),
    ]
    ok = all(item.get("status") == "ok" for item in checks)
    return {
        "status": "ok" if ok else "degraded",
        "service": SERVICE_NAME,
        "uptime_seconds": round(time.time() - STARTED_AT, 1),
        "upstream_sha": upstream_sha(),
        "checks": checks,
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
            processes.append({"name": parts[0], "state": parts[1], "detail": parts[2] if len(parts) > 2 else ""})
    return {"status": "ok" if result.returncode == 0 else "error", "returncode": result.returncode, "processes": processes, "stderr": result.stderr.strip()[:2000]}


def safe_config() -> dict[str, Any]:
    return {
        "values": {key: env(key) for key in SAFE_CONFIG_KEYS if env(key) != ""},
        "secret_presence": {key: bool(env(key)) for key in SECRET_KEYS},
        "ops_locked": not bool(ops_token()),
    }


class OpsHandler(BaseHTTPRequestHandler):
    server_version = "DeerFlowHFSOps/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[ops-service] {self.address_string()} {fmt % args}")

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

    def require_auth(self) -> bool:
        if authorized(self):
            return True
        self.send_json({"error": "unauthorized", "message": "Set DEER_FLOW_OPS_TOKEN and pass Authorization: Bearer <token>."}, 401)
        return False

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if path == "/":
            self.send_html("""<!doctype html><meta charset='utf-8'><title>DeerFlow Ops</title><body><h1>DeerFlow Ops</h1><ul><li><a href='/healthz'>healthz</a></li><li><a href='/readyz'>readyz</a></li><li>/status and /config require Authorization: Bearer token</li></ul></body>""")
            return
        if path == "/healthz":
            self.send_json({"status": "ok", "service": SERVICE_NAME, "component": "ops", "uptime_seconds": round(time.time() - STARTED_AT, 1), "upstream_sha": upstream_sha()})
            return
        if path == "/readyz":
            data = readiness()
            self.send_json(data, 200 if data["status"] == "ok" else 503)
            return
        if not self.require_auth():
            return
        if path == "/status":
            self.send_json({"readiness": readiness(), "supervisor": supervisor_status()})
        elif path == "/config":
            self.send_json(safe_config())
        else:
            self.send_json({"error": "not found"}, 404)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", OPS_PORT), OpsHandler)
    print(f"[ops-service] Listening on 127.0.0.1:{OPS_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
