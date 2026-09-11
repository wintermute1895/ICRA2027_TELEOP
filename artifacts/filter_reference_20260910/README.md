# Formal Joint-Reference Filter Runs (2026-09-10)

This archive contains the compact, public-safe evidence for the first formal
joint-reference filter matrix:

- tasks: button press and screwdriver alignment;
- models: deterministic and CVAE;
- seeds: 7, 17, and 27;
- total runs: 12.

`evidence_freeze.json` is the redacted result manifest. It records aggregate
evaluation metrics, experiment/config/split/reference hashes, checkpoint
hashes, and evidence that was still missing when the matrix was frozen. Raw
episodes, images, per-window predictions, TensorBoard/W&B files, and private
absolute paths are intentionally excluded.

The checkpoint files are copied byte-for-byte from the frozen run directories.
Verify them with:

```bash
sha256sum -c CHECKSUMS.sha256
```

These are offline experimental artifacts, not real-robot deployment releases.
Their embedded deployment status remains `offline_and_simulation_only` and the
filter collection train-deploy contract must pass before hardware use.

