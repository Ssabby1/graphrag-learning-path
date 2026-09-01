#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
VENV_DIR="$BACKEND_DIR/.venv-unix"
EMBEDDINGS=false

usage() {
  cat <<'EOF'
Usage: ./setup.sh [--embeddings]

  (default)       Install the lightweight offline demo. Retrieval falls back to
                  deterministic Unicode hashing when E5 is unavailable.
  --embeddings    Install sentence-transformers and explicitly download the
                  multilingual E5 model into backend/.cache/huggingface.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --embeddings) EMBEDDINGS=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

command -v npm >/dev/null || { echo "Node.js 18+ is required." >&2; exit 1; }

PYTHON_CMD=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null && "$candidate" -c 'import sys; raise SystemExit(not ((3, 11) <= sys.version_info[:2] <= (3, 13)))'; then
    PYTHON_CMD="$candidate"
    break
  fi
done
[[ -n "$PYTHON_CMD" ]] || { echo "Python 3.11-3.13 is required; the default Python may be too new." >&2; exit 1; }

if [[ ! -f "$BACKEND_DIR/.env" ]]; then cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"; fi
if [[ ! -f "$FRONTEND_DIR/.env" ]]; then cp "$FRONTEND_DIR/.env.example" "$FRONTEND_DIR/.env"; fi

if [[ ! -x "$VENV_DIR/bin/python" ]]; then "$PYTHON_CMD" -m venv "$VENV_DIR"; fi
"$VENV_DIR/bin/python" -m pip install --upgrade pip
if [[ "$EMBEDDINGS" == true ]]; then
  "$VENV_DIR/bin/python" -m pip install -r "$BACKEND_DIR/requirements-embeddings.txt"
  echo "Downloading intfloat/multilingual-e5-small (explicit --embeddings mode)..."
  HF_HOME="$BACKEND_DIR/.cache/huggingface" \
    "$VENV_DIR/bin/python" -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"
else
  "$VENV_DIR/bin/python" -m pip install -r "$BACKEND_DIR/requirements.txt"
fi
npm --prefix "$FRONTEND_DIR" ci

if [[ "$EMBEDDINGS" == true ]]; then
  echo "Setup complete with multilingual E5. Run ./start-dev.sh."
else
  echo "Lightweight setup complete. Retrieval will show 'degraded hashing' in the UI."
  echo "Run ./setup.sh --embeddings later for the real multilingual E5 demo."
  echo "Run ./start-dev.sh."
fi
