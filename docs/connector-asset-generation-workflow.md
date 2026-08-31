# Optional GPU asset-generation workflow

The physics baseline never depends on a GPU. Licensed visual assets can be
processed on the configured `ilex24-lan` host with:

```bash
python -B tools/run_connector_asset_generation.py \
  --input /path/to/licensed_laptop.glb \
  --manifest /path/to/licensed_laptop.manifest.json \
  --dry-run
```

Remove `--dry-run` after `ilex24-lan` has a working route and accepts SSH. The
workflow stages the source and manifest remotely, runs
`tools/connector_asset_worker.py` using Blender and CoACD, then copies the
visual OBJ, convex-decomposed collision OBJ, and generated manifest back to
their respective `visual/`, `collision/`, and `manifests/` directories. The
primitive collision baseline is never replaced automatically.

The worker refuses missing license fields and rejects any downloaded asset not
marked `used_for: visual_only`. If the host is unavailable, continue using the
parameterized scene and its existing five validation commands.
