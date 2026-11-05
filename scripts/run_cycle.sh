#!/usr/bin/env bash
# One full pipeline cycle (collect -> clean -> label -> extract -> analyze -> report).
set -euo pipefail
ROOT="${FOODS_ROOT:-/opt/foods}"
cd "$ROOT"
export FOODS_ROOT="$ROOT"
export PYTHONIOENCODING=utf-8
export PYTHONPATH="$ROOT"
"$ROOT/venv/bin/python" -m foods_pipeline.cli run "$@"
