#!/usr/bin/env python3
"""Stage optional mesh processing on ilex24, with a safe local dry-run/fallback."""
from __future__ import annotations

import argparse
import shlex
import socket
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="licensed source mesh")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--host", default="ilex24-lan")
    parser.add_argument("--remote-root", default="/tmp/connector_asset_jobs")
    parser.add_argument("--job", default="usb_c_laptop_visual")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.input.is_file() or not args.manifest.is_file():
        parser.error("--input and --manifest must exist")
    remote_job = f"{args.remote_root.rstrip('/')}/{args.job}"
    local_output = ROOT / "assets/tasks/connector_insertion/visual"
    command = ["ssh", args.host, "mkdir", "-p", remote_job]
    commands = [command, ["scp", str(args.input), f"{args.host}:{remote_job}/source{args.input.suffix}"], ["scp", str(args.manifest), f"{args.host}:{remote_job}/source.manifest.json"], ["scp", str(ROOT / "tools/connector_asset_worker.py"), f"{args.host}:{remote_job}/connector_asset_worker.py"], ["ssh", args.host, "python3", f"{remote_job}/connector_asset_worker.py", "--input", f"{remote_job}/source{args.input.suffix}", "--output", remote_job, "--manifest", f"{remote_job}/source.manifest.json"], ["scp", f"{args.host}:{remote_job}/source{args.input.suffix}", str(local_output)], ["scp", f"{args.host}:{remote_job}/source.manifest.json", str(ROOT / "assets/tasks/connector_insertion/manifests")]]
    print("GPU asset job:", args.job)
    print("fallback:", "parameterized_primitives")
    print("\n".join("$ " + " ".join(shlex.quote(x) for x in cmd) for cmd in commands))
    if args.dry_run:
        return 0
    try:
        socket.gethostbyname(args.host)
    except OSError as exc:
        raise SystemExit(f"host {args.host!r} is not resolvable; use --dry-run or restore SSH/DNS: {exc}")
    for cmd in commands:
        subprocess.run(cmd, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
