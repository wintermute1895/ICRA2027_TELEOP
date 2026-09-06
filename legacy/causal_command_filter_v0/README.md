# Legacy causal command-prior filter v0

This directory preserves the earlier simulation-only ridge command-prior
experiment for historical comparison and reproducibility. It is not the
current flywheel algorithm and is not installed by the main ROS package.

The current learning target is the explicit visual/task-conditioned
`residual_target_rad` model under `src/teleop_filter/`. Do not use this legacy
filter for real hardware or present it as the residual filter.
