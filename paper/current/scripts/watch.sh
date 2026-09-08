#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v latexmk >/dev/null 2>&1; then
  echo "latexmk is required. Install the documented local TeX environment first." >&2
  exit 127
fi

exec latexmk -pvc main.tex
