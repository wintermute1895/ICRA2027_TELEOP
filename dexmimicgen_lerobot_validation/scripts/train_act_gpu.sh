#!/usr/bin/env bash
set -euo pipefail

# For the laptop with a single NVIDIA GPU, either "cuda" or "cuda:0" works.
# CUDA_VISIBLE_DEVICES=0 makes the device selection explicit.
export CUDA_VISIBLE_DEVICES=0
export HF_HOME=/tmp/hf_cache
export TORCH_HOME=/tmp/torch_home

PYTHONNOUSERSITE=1 /home/pao/miniconda3/envs/dex_teleop/bin/python -m lerobot.scripts.train \
  --policy.type=act \
  --dataset.repo_id=dexmimicgen_two_arm_can_sort_subset \
  --dataset.root=/home/pao/文档/ChatGPT/论文/lerobot_data/dexmimicgen_can_sort_subset_clean \
  --dataset.video_backend=pyav \
  --policy.device=cuda \
  --policy.use_amp=true \
  --policy.push_to_hub=false \
  --policy.pretrained_backbone_weights=null \
  --batch_size=16 \
  --steps=1000 \
  --eval_freq=0 \
  --log_freq=10 \
  --save_freq=250 \
  --save_checkpoint=true \
  --num_workers=4 \
  --output_dir=/home/pao/文档/ChatGPT/论文/outputs/act_gpu_run \
  --wandb.enable=false
