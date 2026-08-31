#!/usr/bin/env bash

resolve_training_env_prefix() {
  if [[ -n "${LEROBOT_ENV_PREFIX:-}" ]]; then
    printf '%s\n' "$LEROBOT_ENV_PREFIX"
    return 0
  fi
  local conda_bin="${CONDA_BIN:-}"
  if [[ -z "$conda_bin" ]]; then
    conda_bin="$(command -v conda 2>/dev/null || true)"
  fi
  if [[ -z "$conda_bin" && -x "$HOME/miniconda3/bin/conda" ]]; then
    conda_bin="$HOME/miniconda3/bin/conda"
  fi
  if [[ -z "$conda_bin" && -x "$HOME/miniforge3/bin/conda" ]]; then
    conda_bin="$HOME/miniforge3/bin/conda"
  fi
  [[ -x "$conda_bin" ]] || return 1
  local base name
  base="$($conda_bin info --base)" || return 1
  name="${LEROBOT_ENV_NAME:-teleop-train}"
  printf '%s/envs/%s\n' "$base" "$name"
}

resolve_conda_bin() {
  if [[ -n "${CONDA_BIN:-}" && -x "$CONDA_BIN" ]]; then
    printf '%s\n' "$CONDA_BIN"
  elif command -v conda >/dev/null 2>&1; then
    command -v conda
  elif [[ -x "$HOME/miniconda3/bin/conda" ]]; then
    printf '%s\n' "$HOME/miniconda3/bin/conda"
  elif [[ -x "$HOME/miniforge3/bin/conda" ]]; then
    printf '%s\n' "$HOME/miniforge3/bin/conda"
  else
    return 1
  fi
}
