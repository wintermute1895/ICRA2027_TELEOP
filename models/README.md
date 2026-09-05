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

## Shadow / adapter startup

Full inference still requires the `teleop-train` environment with LeRobot and
CUDA.  Once available:

```bash
bash scripts/start_act_adapter.sh config/runtime/act-button-A.yaml
```

The adapter only publishes a candidate under `/act/right_arm_joint_control`;
the model deployment supervisor is the intended bridge to the robot.
