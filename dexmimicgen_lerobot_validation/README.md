# DexMimicGen -> LeRobot ACT first-phase validation

This workspace validates the infrastructure path:

1. Download DexMimicGen/Robomimic HDF5.
2. Convert Robomimic HDF5 to a local LeRobot dataset.
3. Train a minimal ACT policy.
4. Load the checkpoint and rollout in Robosuite.

## Environment

Use the Conda environment:

```bash
conda activate /home/pao/miniconda3/envs/dex_teleop
```

Key pinned versions are recorded by the environment itself. The rollout currently
uses MuJoCo 3.3.6 and mink 1.0.0 to support `WHOLE_BODY_MINK_IK`.

## Main scripts

```bash
python scripts/convert_robomimic_to_lerobot.py --help
python scripts/rollout_act_robosuite.py --help
```

## Data

The 4.43GB source HDF5 is intentionally not committed. Download it into `data/`:

```bash
wget -c -O data/two_arm_can_sort_random.hdf5 \
  'https://hf-mirror.com/datasets/MimicGen/dexmimicgen_datasets/resolve/main/generated/two_arm_can_sort_random.hdf5?download=true'
```

The small converted dataset and rollout artifacts are tracked in this repository.
