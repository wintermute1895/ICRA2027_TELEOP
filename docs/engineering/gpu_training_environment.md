# GPU Training Environment

The Codex sandbox may not expose the host NVIDIA device or driver. A sandbox
result of `torch.cuda.is_available() == false` is therefore not evidence that
the real training workstation lacks a GPU.

Before formal flywheel or ACT training, run the checks in the actual training
environment (currently the `teleop-train` environment):

```bash
nvidia-smi
python -c 'import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.device_count())'
```

Run the trainer with `--device cuda --require-cuda`. The training report must
record a `cuda` device. CPU runs are valid only for smoke tests and must not be
used as formal flywheel results.
