# DexMimicGen -> LeRobot ACT first-phase validation

This workspace validates the infrastructure path:

1. Download DexMimicGen/Robomimic HDF5.
2. Convert Robomimic HDF5 to a local LeRobot dataset.
3. Train a minimal ACT policy.
4. Load the checkpoint and rollout in Robosuite.

## Environment

Use the Conda environment (the environment manager, not the LeRobot
installation source):

```bash
conda activate /home/pao/miniconda3/envs/dex_teleop
```

Install the pinned LeRobot release from PyPI with `pip`:

```bash
python -m pip install lerobot==0.3.2
```

Verify the installation:

```bash
python -m pip show lerobot
python -c "import lerobot; print(lerobot.__version__)"
```

The validated installation is `lerobot==0.3.2` from PyPI. It is not a source
checkout, so there is no local Git repository or source commit hash to pin.
Other pinned versions are recorded in the acceptance report below. The rollout
currently uses MuJoCo 3.3.6 and mink 1.0.0 to support `WHOLE_BODY_MINK_IK`.

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

## D0 right arm + O6 bags

The D0 bags use a separate bridge because they are ROS2 bags rather than
Robomimic HDF5.  With the ROS Humble environment sourced, extract the color
image, right-arm state/command, and O6 command streams from selected episodes:

```bash
source ../scripts/d0_env.sh
/usr/bin/python3 scripts/extract_d0_bags.py \
  --bags ../d0_data/d0_right_hand_005/bag ../d0_data/d0_right_hand_008/bag \
  --output-dir ../d0_act_data/extracted --fps 10
```

Then use the `dex_teleop` Conda environment to create a LeRobot dataset:

```bash
PYTHONNOUSERSITE=1 /home/pao/miniconda3/envs/dex_teleop/bin/python \
  scripts/convert_d0_to_lerobot.py \
  --input-dir ../d0_act_data/extracted \
  --output-root ../d0_act_data/lerobot_o6_005_008 \
  --repo-id d0_right_arm_o6_005_008 --fps 10
```

The resulting ACT state and action are 13-dimensional: seven right-arm
joint values followed by six O6 values.  O6 has no driver state topic in this
stack, so its state component uses the recorded six-joint command stream.
The 20-step CPU smoke test used for this dataset is:

```bash
HF_HOME=/tmp/hf_cache_d0 HF_DATASETS_CACHE=/tmp/hf_cache_d0/datasets \
PYTHONNOUSERSITE=1 /home/pao/miniconda3/envs/dex_teleop/bin/python -m lerobot.scripts.train \
  --policy.type=act --dataset.repo_id=d0_right_arm_o6_005_008 \
  --dataset.root=../d0_act_data/lerobot_o6_005_008 \
  --policy.device=cpu --policy.repo_id=d0_act_smoke_005_008 \
  --policy.push_to_hub=false --policy.pretrained_backbone_weights=null \
  --batch_size=2 --steps=20 --eval_freq=0 --save_freq=20 \
  --save_checkpoint=true --num_workers=0 \
  --output_dir=../d0_act_data/act_smoke_005_008 --wandb.enable=false
```
