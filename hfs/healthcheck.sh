#!/usr/bin/env bash
set -Eeuo pipefail

curl -fsS --max-time 5 http://127.0.0.1:7860/_ops/readyz >/dev/null
