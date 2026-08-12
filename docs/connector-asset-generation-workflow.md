# Optional GPU asset-generation workflow

The physics baseline never depends on a GPU. Licensed visual assets can be
processed on the configured `ilex24-lan` host with:

```bash
python -B tools/run_connector_asset_generation.py \
  --input /path/to/licensed_laptop.glb \
  --manifest /path/to/licensed_laptop.manifest.json \
  --dry-run
```

Remove `--dry-run` after `ilex24-lan` has a working route and accepts SSH. The workflow stages
the source and manifest remotely, runs `tools/connector_asset_worker.py`, and
copies only the visual result back to
`assets/tasks/connector_insertion/visual/`. The primitive collision baseline is
never replaced automatically. CoACD/Blender processing can be added inside the
worker once those tools are installed on the GPU host.

The worker refuses missing license fields and rejects any downloaded asset not
marked `used_for: visual_only`. If the host is unavailable, continue using the
parameterized scene and its existing five validation commands.
