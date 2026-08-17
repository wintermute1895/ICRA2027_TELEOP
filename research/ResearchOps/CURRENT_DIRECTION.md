# Active Research Direction

Status: active as of 2026-08-17.

The authoritative detailed discussion record is [论文讨论会议文档8_16.pdf](discussions/论文讨论会议文档8_16.pdf).

## Core Question

Can a context-conditioned causal command filter, trained by self-supervision on task-valid teleoperation demonstrations, improve the yield of task-valid demonstrations per active operator minute for precision insertion under a fixed safety envelope?

## Active Contributions

- A task-conditioned collection and episode-admission contract for grasp-conditioned, visible, reference-feasible, configuration-varying precision insertion.
- A quality-gated, self-supervised, context-conditioned causal command filter with bounded online assistance and fixed safety projection.
- A fixed-resource comparison of `F_rule`, `F_static`, and `F_flywheel`, with `task-valid episodes / active operator minute` as the primary outcome.

ACT is an optional frozen downstream utility study, not filter supervision or an episode-admission signal.

## Superseded Direction

The reference-relative corrective-allocation RFC path is archived in [archive/rfc_superseded](archive/rfc_superseded). It is historical context only and must not define active claims, methods, or experiments.
