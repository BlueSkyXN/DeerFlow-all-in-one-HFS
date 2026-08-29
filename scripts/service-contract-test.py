#!/usr/bin/env python3
"""Dependency-free integration checks for the HFS ops/admin services."""

from __future__ import annotations

import http.client
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def request(
    port: int,
    path: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    payload = response.read()
    response_headers = dict(response.getheaders())
    connection.close()
    return response.status, response_headers, payload


def wait_ready(port: int, path: str, process: subprocess.Popen[str]) -> None:
    deadline = time.time() + 10
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"service exited before readiness: {output}")
        try:
            if request(port, path)[0] == 200:
                return
        except OSError:
            pass
        time.sleep(0.1)
    raise TimeoutError(f"service on port {port} did not become ready")


def check(name: str, actual: Any, expected: Any, completed: list[str]) -> None:
    if actual != expected:
        raise AssertionError(f"{name}: got {actual!r}, expected {expected!r}")
    completed.append(name)


def json_body(payload: bytes) -> dict[str, Any]:
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise AssertionError(f"expected object response, got {type(data).__name__}")
    return data


def main() -> None:
    ops_port = free_port()
    admin_port = free_port()
    completed: list[str] = []

    with tempfile.TemporaryDirectory(prefix="deerflow-hfs-services-") as temp_dir:
        root = Path(temp_dir)
        runtime_home = root / "runtime"
        log_dir = runtime_home / "logs"
        database_dir = runtime_home / "data"
        upstream_root = root / "upstream"
        fake_bin = root / "bin"
        for path in (
            log_dir,
            database_dir,
            runtime_home / "run",
            runtime_home / "threads",
            runtime_home / "uploads",
            upstream_root,
            fake_bin,
        ):
            path.mkdir(parents=True, exist_ok=True)

        (runtime_home / ".hfs-persistence-probe").write_text("ok\n", encoding="utf-8")
        (runtime_home / "config.yaml").write_text("{}\n", encoding="utf-8")
        (runtime_home / "extensions_config.json").write_text("{}\n", encoding="utf-8")
        (database_dir / "deerflow.db").write_bytes(b"")
        (upstream_root / ".deerflow-upstream-sha").write_text(
            "a" * 40 + "\n", encoding="utf-8"
        )
        (upstream_root / ".deerflow-upstream-ref").write_text(
            "a" * 40 + "\n", encoding="utf-8"
        )
        (upstream_root / ".deerflow-upstream-version").write_text(
            "2.1.0\n", encoding="utf-8"
        )

        log_lines = [
            f"ERROR token=ops-secret Authorization: Bearer external-secret postgresql://user:db-secret@example.invalid/db line={index}"
            for index in range(15)
        ]
        (log_dir / "admin-actions.jsonl").write_text(
            "\n".join(log_lines) + "\n", encoding="utf-8"
        )

        supervisorctl = fake_bin / "supervisorctl"
        supervisorctl.write_text(
            "#!/bin/sh\n"
            'printf "gateway RUNNING pid 1, uptime 0:01:00\\n"\n'
            'printf "frontend RUNNING pid 2, uptime 0:01:00\\n"\n'
            'printf "nginx RUNNING pid 3, uptime 0:01:00\\n"\n',
            encoding="utf-8",
        )
        supervisorctl.chmod(0o755)

        nginx_bin = shutil.which("true")
        if not nginx_bin:
            raise RuntimeError(
                "true command is required for the admin health-check fixture"
            )
        nginx_config = root / "nginx.conf"
        nginx_config.write_text("", encoding="utf-8")

        environment = os.environ.copy()
        environment.update(
            {
                "PATH": str(fake_bin) + os.pathsep + environment.get("PATH", ""),
                "DEER_FLOW_PROJECT_ROOT": str(upstream_root),
                "DEER_FLOW_HOME": str(runtime_home),
                "DEER_FLOW_DB_DIR": str(database_dir),
                "DEER_FLOW_CONFIG_PATH": str(runtime_home / "config.yaml"),
                "DEER_FLOW_EXTENSIONS_CONFIG_PATH": str(
                    runtime_home / "extensions_config.json"
                ),
                "DEER_FLOW_OPS_PORT": str(ops_port),
                "OPS_TOKEN": "ops-secret",
                "DEER_FLOW_OPS_DEFAULT_CHECKS_ENABLED": "false",
                "DEER_FLOW_OPS_LOG_DIR": str(log_dir),
                "DEER_FLOW_OPS_COOKIE_SECURE": "false",
                "DEER_FLOW_ADMIN_PORT": str(admin_port),
                "DEER_FLOW_ADMIN_ENABLED": "true",
                "DEER_FLOW_ADMIN_ACTIONS_ENABLED": "false",
                "ADMIN_PASSWORD": "admin-secret",
                "DEER_FLOW_NGINX_BIN": nginx_bin,
                "DEER_FLOW_NGINX_CONFIG": str(nginx_config),
            }
        )

        processes = [
            subprocess.Popen(
                ["python3", str(REPO_ROOT / "hfs/services/ops_service.py")],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            ),
            subprocess.Popen(
                ["python3", str(REPO_ROOT / "hfs/services/admin_service.py")],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            ),
        ]

        try:
            wait_ready(ops_port, "/healthz", processes[0])
            wait_ready(admin_port, "/", processes[1])

            check(
                "ops public healthz", request(ops_port, "/healthz")[0], 200, completed
            )
            check("ops public readyz", request(ops_port, "/readyz")[0], 200, completed)
            check("ops unauthorized", request(ops_port, "/status")[0], 401, completed)

            status, headers, _ = request(
                ops_port, "/status", headers={"X-Ops-Token": "ops-secret"}
            )
            check("ops header auth", status, 200, completed)
            check(
                "ops header auth takes precedence over gateway bearer",
                request(
                    ops_port,
                    "/status",
                    headers={
                        "Authorization": "Bearer hf-gateway-token",
                        "X-Ops-Token": "ops-secret",
                    },
                )[0],
                200,
                completed,
            )
            session_cookie = headers.get("Set-Cookie", "")
            check(
                "ops session is HttpOnly", "HttpOnly" in session_cookie, True, completed
            )
            check(
                "ops session is SameSite Strict",
                "SameSite=Strict" in session_cookie,
                True,
                completed,
            )
            cookie = session_cookie.split(";", 1)[0]
            check(
                "ops cookie auth",
                request(ops_port, "/version", headers={"Cookie": cookie})[0],
                200,
                completed,
            )

            status, headers, _ = request(ops_port, "/?token=ops-secret")
            check("ops query token is not accepted", status, 200, completed)
            check(
                "ops query token creates no session",
                "Set-Cookie" in headers,
                False,
                completed,
            )

            status, _, payload = request(
                ops_port, "/version", headers={"X-Ops-Token": "ops-secret"}
            )
            check("ops version", status, 200, completed)
            version = json_body(payload)["version"]
            check("ops upstream sha", version["upstream_sha"], "a" * 40, completed)
            check(
                "ops upstream version", version["upstream_version"], "2.1.0", completed
            )
            check(
                "ops metrics",
                request(ops_port, "/metrics", headers={"X-Ops-Token": "ops-secret"})[0],
                200,
                completed,
            )

            status, _, payload = request(
                ops_port,
                "/logs?service=admin-actions&lines=20",
                headers={"X-Ops-Token": "ops-secret"},
            )
            check("ops logs", status, 200, completed)
            content = json_body(payload)["content"]
            check(
                "ops known secret redaction", "ops-secret" in content, False, completed
            )
            check(
                "ops bearer redaction", "external-secret" in content, False, completed
            )
            check(
                "ops URL password redaction", "db-secret" in content, False, completed
            )
            check(
                "ops unknown log rejected",
                request(
                    ops_port,
                    "/logs?service=../../etc/passwd",
                    headers={"X-Ops-Token": "ops-secret"},
                )[0],
                404,
                completed,
            )

            status, _, payload = request(
                ops_port,
                "/errors?lines=20&limit=3",
                headers={"X-Ops-Token": "ops-secret"},
            )
            check("ops errors", status, 200, completed)
            errors = json_body(payload)
            check("ops errors total count", errors["count"], 15, completed)
            check("ops errors response cap", len(errors["matches"]), 3, completed)
            check(
                "ops grouped errors response cap",
                len(errors["groups"][0]["matches"]),
                3,
                completed,
            )
            shutil.rmtree(log_dir)
            shutil.rmtree(runtime_home / "run")
            status, _, payload = request(
                ops_port, "/persistence", headers={"X-Ops-Token": "ops-secret"}
            )
            check("ops persistence", status, 200, completed)
            persistence = json_body(payload)
            check("ops persistence status", persistence["status"], "ok", completed)
            observed_paths = {
                item["name"]: item["status"]
                for item in persistence["observed_paths"]
            }
            check(
                "ops persistence observes missing logs",
                observed_paths["logs"],
                "error",
                completed,
            )
            check(
                "ops persistence observes missing run",
                observed_paths["run"],
                "error",
                completed,
            )

            check("admin public shell", request(admin_port, "/")[0], 200, completed)
            check(
                "admin unauthorized",
                request(admin_port, "/api/status")[0],
                401,
                completed,
            )
            admin_headers = {"Authorization": "Bearer admin-secret"}
            check(
                "admin status",
                request(admin_port, "/api/status", headers=admin_headers)[0],
                200,
                completed,
            )
            check(
                "admin actions",
                request(admin_port, "/api/actions", headers=admin_headers)[0],
                200,
                completed,
            )
            check(
                "admin audit",
                request(admin_port, "/api/audit?limit=5", headers=admin_headers)[0],
                200,
                completed,
            )
            check(
                "admin health guard missing",
                request(
                    admin_port,
                    "/api/actions/run-health-checks",
                    method="POST",
                    headers=admin_headers,
                )[0],
                403,
                completed,
            )
            guarded_headers = {
                **admin_headers,
                "X-DeerFlow-Admin-Intent": "DeerFlow-HFS-Admin",
                "X-DeerFlow-Admin-Confirm": "run-health-checks",
            }
            check(
                "admin health action",
                request(
                    admin_port,
                    "/api/actions/run-health-checks",
                    method="POST",
                    headers=guarded_headers,
                )[0],
                200,
                completed,
            )
            status, _, payload = request(
                admin_port, "/api/audit?limit=5", headers=admin_headers
            )
            check("admin health action audit", status, 200, completed)
            audit_events = json_body(payload)["events"]
            check(
                "admin health action recorded",
                any(
                    event.get("action") == "run-health-checks"
                    for event in audit_events
                    if isinstance(event, dict)
                ),
                True,
                completed,
            )
            write_headers = {
                **admin_headers,
                "X-DeerFlow-Admin-Intent": "DeerFlow-HFS-Admin",
                "X-DeerFlow-Admin-Confirm": "reload-nginx",
            }
            check(
                "admin writes disabled",
                request(
                    admin_port,
                    "/api/reload-nginx",
                    method="POST",
                    headers=write_headers,
                )[0],
                403,
                completed,
            )
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

    print(f"service-contract-test: ok ({len(completed)} checks)")


if __name__ == "__main__":
    main()
