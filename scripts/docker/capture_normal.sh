#!/usr/bin/env bash
# Trafico de alumnos (baseline del campus). Uso: capture_normal.sh [segundos]
set -euo pipefail
cd "$(dirname "$0")"
DURATION="${1:-120}"
exec bash ./capture_campus.sh baseline "$DURATION"
