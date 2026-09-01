#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_DIR="$PROJECT_ROOT/.codex-tmp/runtime"
VENV_DIR="$PROJECT_ROOT/backend/.venv-unix"

[[ -x "$VENV_DIR/bin/python" ]] || { echo "Run ./setup.sh first." >&2; exit 1; }
mkdir -p "$RUN_DIR"
cd "$PROJECT_ROOT/backend"
GRAPH_BACKEND="${GRAPH_BACKEND:-csv}" \
GRAPH_CONCEPTS_CSV="${GRAPH_CONCEPTS_CSV:-$PROJECT_ROOT/data/seed/concepts.csv}" \
GRAPH_RELATIONS_CSV="${GRAPH_RELATIONS_CSV:-$PROJECT_ROOT/data/seed/relations.csv}" \
HF_HOME="${HF_HOME:-$PROJECT_ROOT/backend/.cache/huggingface}" \
LLM_ENABLED="${LLM_ENABLED:-false}" \
PYTHONPATH=. "$VENV_DIR/bin/python" run.py >"$RUN_DIR/backend.log" 2>&1 &
echo $! >"$RUN_DIR/backend.pid"

cd "$PROJECT_ROOT/frontend"
npm run dev >"$RUN_DIR/frontend.log" 2>&1 &
echo $! >"$RUN_DIR/frontend.pid"

echo "Frontend: http://127.0.0.1:5173"
echo "API docs: http://127.0.0.1:8000/docs"
echo "Graph backend: public CSV sample"
echo "Logs: $RUN_DIR"
