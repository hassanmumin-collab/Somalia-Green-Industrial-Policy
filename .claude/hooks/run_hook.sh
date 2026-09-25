#!/usr/bin/env bash
# Finds a Python interpreter that has PyYAML (project venv first, then python3, then python)
# and runs tools/hook.py with the hook JSON on stdin.
ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
for PY in "$ROOT/.venv/Scripts/python.exe" "$ROOT/.venv/bin/python" python3 python; do
  if "$PY" -c "import yaml" >/dev/null 2>&1; then
    exec "$PY" "$ROOT/tools/hook.py" "$@"
  fi
done
echo "Verifier hook: no Python interpreter with PyYAML found. Run: uv venv --python 3.12 .venv && uv pip install --python .venv/Scripts/python.exe -r requirements.txt" >&2
exit 1
