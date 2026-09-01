#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
VENV_DIR="$BACKEND_DIR/.venv-unix"

command -v python3 >/dev/null || { echo "Python 3 is required." >&2; exit 1; }
command -v npm >/dev/null || { echo "Node.js 18+ is required." >&2; exit 1; }

if [[ ! -f "$BACKEND_DIR/.env" ]]; then cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"; fi
if [[ ! -f "$FRONTEND_DIR/.env" ]]; then cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"; fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then python3 -m venv "$VENV_DIR"; fi
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"
npm --prefix "$FRONTEND_DIR" ci

echo "Setup complete. Run ./start-dev.sh."
