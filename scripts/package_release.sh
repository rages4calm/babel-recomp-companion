#!/usr/bin/env bash
# Compatibility entry point: validates build identity, notices and player data.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${PYTHON:-python3}" "$ROOT/scripts/package_release.py" "${1:?build directory}" "${2:?platform tag}"
