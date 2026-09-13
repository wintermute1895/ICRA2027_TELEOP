# Local model artifacts

This directory holds model weights for local deployment and testing.  Large
model files are intentionally ignored by Git; they must be re-provisioned on a
new machine from the signed deployment packages.

## act_button_A

Source package:

```text
/home/fanshihao/Desktop/act_deployment/act_button_A_deployment.tar.gz
```

Runtime config:

```text
config/runtime/act-button-A.yaml
```

Model layout:

```text
models/act_button_A/
├── checkpoints/last/pretrained_model/
│   ├── config.json
│   ├── model.safetensors
│   └── train_config.json
└── stats.json
```

Checkpoint directory SHA-256:

```text
f48e62ad4d7ff2ba80dad6e90935a98f4dc38ebd24a4db2a938a412711c0b2f4
```

Model contract: 7D right-arm state/action, two RGB cameras (main_rgb,
auxiliary_rgb), image size 480x640.

## Verification

```bash
bash scripts/validate_act_deployment.sh config/runtime/act-button-A.yaml
```

Optional: regenerate a promoted config from the local checkpoint:

```bash
python tools/promote_runtime_model.py --kind act \
  --checkpoint models/act_button_A/checkpoints/last/pretrained_model \
  --dataset-stats models/act_button_A/stats.json \
  --output /tmp/act-button-A-verify.yaml
```

The output config must contain the checkpoint SHA-256 listed above.

## Adapter startup

Full inference still requires the `teleop-train` environment with LeRobot and
CUDA.  Once available:

```bash
bash scripts/start_act_adapter.sh config/runtime/act-button-A.yaml
```

The adapter only publishes a candidate under `/act/right_arm_joint_control`;
the model deployment supervisor is the intended bridge to the robot.

## task2_imle

Source checkpoint (SJ01):

```text
/media/dex/cx_Data/imle/task2_power_button_press/checkpoints/task2_power_button_press_20260911T153358Z/latest_deployment.pt
```

Runtime template:

```text
config/runtime/imle-task2.yaml
```

Model contract: 7D right-arm state/action in LinkerTA degrees, two RGB cameras
(main_rgb, auxiliary_rgb), image size 480x640, 50 Hz, obs_horizon=2,
pred_horizon=16, action_horizon=8, 20 overlap-selected candidates.

## IMLE verification

```bash
bash scripts/promote_model_checkpoint.sh --kind imle \
  --checkpoint /path/to/latest_deployment.pt \
  --output /tmp/imle-task2-promoted.yaml
bash scripts/validate_imle_deployment.sh /tmp/imle-task2-promoted.yaml
bash scripts/start_imle_adapter.sh /tmp/imle-task2-promoted.yaml
```

Full Linux steps: `docs/engineering/IMLE_DEPLOYMENT.md`.

## filter/task3_screwdriver

Local-only learned-gain filter checkpoint received 2026-09-13. It is stored
outside Git because `/models/*` is intentionally ignored.

Checkpoint:

```text
models/filter/task3_screwdriver/cvae_rate_limited_best_prior_mae_epoch50.pt
```

Provenance and contract:

- source filename: `best_prior_mae.pt`
- task: Task3 `screwdriver_alignment_v1`
- model: `cvae_rate_limited`, 899,809 parameters
- target: `joint_reference_action_rad`, `delta_from_last_executed`
- selection: epoch 50, `validation.prior_mae_rad`
- learned authority: `gain_enabled=true`, `gate_enabled=true`, `authority_mode=rate_limited`
- joint-reference config SHA-256: `4ca5fc24330fd687429750aaa10867d8c009bb94a432a1d09ae62f679efa5ef8`
- checkpoint SHA-256: `82e660227f8b20a7b8ef3b0a33cda6d0ae57743bf5fd076398f6f94c081b1399`

This checkpoint is not interchangeable with the frozen action-only
`screwdriver/cvae_seed*.pt` references: those have no gain or gate heads and
can only run through explicit fixed gain. This checkpoint is the learned-alpha
candidate and should be deployed with `authority.mode=checkpoint` when it is
validated on hardware.
