#!/usr/bin/env python3
"""Orchestrate optional Blender and CoACD asset processing on ilex24-lan."""
from __future__ import annotations

import argparse
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="licensed source mesh (.obj/.stl/.ply/.glb/.gltf)")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--host", default="ilex24-lan")
    parser.add_argument("--remote-root", default="/tmp/connector_asset_jobs")
    parser.add_argument("--job", default="usb_c_laptop_visual")
    parser.add_argument("--name", help="asset output stem")
    parser.add_argument("--coacd-threshold", type=float, default=0.05)
    parser.add_argument("--max-convex-hull", type=int, default=32)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.input.is_file() or not args.manifest.is_file():
        parser.error("--input and --manifest must exist")
    remote_job = f"{args.remote_root.rstrip('/')}/{args.job}"
    remote_input = f"{remote_job}/source{args.input.suffix.lower()}"
    worker = f"{remote_job}/connector_asset_worker.py"
    asset_name = args.name or args.input.stem
    name_args = [] if not args.name else ["--name", args.name]
    worker_args = ["~/.venvs/connector-assets/bin/python", worker, "--input", remote_input, "--output", remote_job, "--manifest", f"{remote_job}/source.manifest.json", "--coacd-threshold", str(args.coacd_threshold), "--max-convex-hull", str(args.max_convex_hull), *name_args]
    commands = [
        ["ssh", args.host, "mkdir", "-p", remote_job],
        ["scp", str(args.input.resolve()), f"{args.host}:{remote_input}"],
        ["scp", str(args.manifest.resolve()), f"{args.host}:{remote_job}/source.manifest.json"],
        ["scp", str(ROOT / "tools/connector_asset_worker.py"), f"{args.host}:{worker}"],
        ["ssh", args.host, *worker_args],
        ["scp", f"{args.host}:{remote_job}/visual/{asset_name}.obj", str(ROOT / "assets/tasks/connector_insertion/visual")],
        ["scp", f"{args.host}:{remote_job}/collision/{asset_name}_coacd.obj", str(ROOT / "assets/tasks/connector_insertion/collision")],
        ["scp", f"{args.host}:{remote_job}/manifests/{asset_name}.manifest.json", str(ROOT / "assets/tasks/connector_insertion/manifests")],
    ]
    print("GPU asset job:", args.job)
    print("fallback: parameterized_primitives")
    print("\n".join("$ " + " ".join(shlex.quote(item) for item in command) for command in commands))
    if args.dry_run:
        return 0
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
