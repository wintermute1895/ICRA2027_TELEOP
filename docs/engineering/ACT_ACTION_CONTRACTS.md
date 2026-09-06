# ACT action contracts

The primary policy contract is `arm7`: the seven right-arm joint positions.
Hand channels are not part of the main ACT policy because they make the policy
learn grasp semantics and arm motion together, while the current deployment
supervisor and bridge are arm-first.

`arm7_hand6` remains available for exploratory O6 experiments and for reading
the existing 13D dataset. Both contracts are defined in
`config/act/action_contracts.yaml` and are selected at the JSONL-to-LeRobot
boundary, so the canonical episode remains unchanged.

## Conversion

The normal conversion produces the 7D dataset:

```bash
bash scripts/convert_episode_to_lerobot.sh \
  --run-dir /path/to/run
```

For an exploratory 13D run:

```bash
bash scripts/convert_episode_to_lerobot.sh \
  --run-dir /path/to/run \
  --action-contract arm7_hand6
```

The selected contract is recorded in the LeRobot feature names and should be
copied into the training and deployment manifest. Do not mix contracts within
one dataset or checkpoint.
