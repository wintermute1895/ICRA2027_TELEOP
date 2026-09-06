#!/usr/bin/env bash
# One-command, GUI-managed robot teleoperation capture launcher.
#
# All real-hardware safety confirmations remain mandatory CLI flags and are
# validated by scripts/start_capture_session.sh before this wrapper reaches the
# GUI.  Safe observation mode (no --real) does not require the confirmations.
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

exec bash "$ROOT_DIR/scripts/start_capture_session.sh" --manager=gui "$@"
