#!/bin/sh
# Thin wrapper around install.py — installs the deye-* skill suite.
# Forwards all arguments, e.g.:  ./install.sh --scope local
set -e
DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "[ERR] Python not found on PATH. Install Python 3.8+." >&2
    exit 1
fi
exec "$PY" "$DIR/install.py" "$@"
