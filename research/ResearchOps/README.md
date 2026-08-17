# ResearchOps

This directory contains the evidence and experiment plan for the active precision-insertion teleoperation study. It does not control the robot or replace the primary data recorder.

## Active Direction

Read [CURRENT_DIRECTION.md](CURRENT_DIRECTION.md) first. The detailed discussion-meeting record is [论文讨论会议文档8_16.pdf](discussions/论文讨论会议文档8_16.pdf).

The active research question is whether a quality-audited, self-supervised, context-conditioned causal command filter can increase task-valid precision-insertion demonstrations per active operator minute under a fixed safety envelope.

The primary experimental comparison is `F_rule` versus `F_static` versus `F_flywheel`. A downstream ACT study is secondary and does not influence episode admission or filter training.

## Evidence and Literature

- `papers/` contains verified paper cards and unverified search candidates.
- `reports/` contains generated local reports and is not committed by default.
- `tools/` contains read-only research-audit utilities that remain relevant to active work.

## Archived RFC Direction

[archive/rfc_superseded](archive/rfc_superseded) contains the prior reference-relative corrective-allocation RFC draft, claims, experiment indexes, configurations, and provenance validator. These materials are preserved for historical traceability but must not be used as active claims, methods, or experiment plans.

## Research Boundary

ResearchOps consumes recorded episode artifacts and offline audit results. Real-time teleoperation, synchronization, and safety enforcement remain in the main repository infrastructure.
