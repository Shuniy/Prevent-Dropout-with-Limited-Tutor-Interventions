#!/usr/bin/env bash
# One interpreter choice for python, python3, pip and editable installation.
set -euo pipefail
cd "$(dirname "$0")/.."
environment_dir="${1:-.venv}"
project_python="$(cat .python-version)"
if [[ "$project_python" != "3.13" ]]; then
  echo "The active project requires Python 3.13." >&2
  exit 1
fi
if [[ -e "$environment_dir" ]]; then
  if [[ ! -x "$environment_dir/bin/python" ]] || ! "$environment_dir/bin/python" -c 'import sys; sys.exit(sys.version_info[:2] != (3,13))'; then
    echo "Existing environment uses another interpreter. Choose a fresh environment directory as the first argument." >&2
    exit 1
  fi
elif command -v uv >/dev/null 2>&1; then
  uv venv --python "$project_python" --seed "$environment_dir"
else
  python3.13 -m venv "$environment_dir"
fi
"$environment_dir/bin/python" --version
"$environment_dir/bin/python" -m pip install -r requirements-offline.txt
"$environment_dir/bin/python" -m pip install --no-deps -e .
echo "Activate with: source $environment_dir/bin/activate"
