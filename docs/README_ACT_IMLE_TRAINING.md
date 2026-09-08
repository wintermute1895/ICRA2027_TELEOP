# ACT / IMLE 数据转换与训练操作手册

本文说明采集完成后，如何把 ROS bag 转换为 LeRobot 数据，并分别训练 ACT 与
IMLE。命令按当前远端工作站 `dex@100.69.71.73` 的目录编写。训练、缓存和
checkpoint 使用 ext4 数据卷 `/media/dex/data`；原始采集保留在 Cyan 数据盘，
转换器不会删除原始 rosbag。

## 1. 当前 Task 3 数据

| 项目 | 值 |
| --- | --- |
| 原始数据 | `/media/dex/Cyan_data/Task_Data/task3_Data` |
| LeRobot 数据 | `/media/dex/data/lerobot_task3_screwdriver_alignment_50hz` |
| repo id | `linker_a7_task3_screwdriver_alignment` |
| task | `screwdriver_alignment_v1` |
| 频率 | 50 Hz |
| 相机 | `main_rgb`、`auxiliary_rgb`，480×640 RGB |
| 状态/动作 | 右臂 7 关节，单位 rad |
| 转换结果 | 100 条源记录；96 成功，4 条明确跳过；73,822 帧 |

4 条跳过记录的 `.db3.zstd` 都报告 `Read error (39): premature end`。它们仍在
`conversion_report.json` 中保留 run id 和失败原因，没有被静默丢弃。

## 2. 目录与环境

```bash
CONVERTER_ROOT=/home/dex/桌面/DexC/DexCatch-wjl/dexmimicgen_lerobot_validation
IMLE_ROOT=/home/dex/桌面/ICRA2027_TELEOP_IMLE
PYTHON=/home/dex/桌面/ICRA2027_TELEOP/.conda/envs/dex_teleop/bin/python
SOURCE_ROOT=/media/dex/Cyan_data/Task_Data/task3_Data
DATASET_ROOT=/media/dex/data/lerobot_task3_screwdriver_alignment_50hz
RUNTIME_ROOT=/media/dex/data/imle_runtime
```

不要把 ACT checkpoint 写到 `/media/dex/Cyan_data`。该文件系统不支持 LeRobot
创建 `checkpoints/last` 符号链接，会在已经保存权重后报
`PermissionError: Operation not permitted`。使用 `/media/dex/data` 可避免这个问题。

ACT 和 IMLE 不应同时占用同一张 4090 训练。它们可以共用转换结果，但必须使用
独立输出目录和 checkpoint。

## 3. 转换 rosbag 为 LeRobot

### 3.1 首次转换

输出目录必须不存在或为空。先启动正式转换：

```bash
mkdir -p /media/dex/data/imle_runtime
cd /home/dex/桌面/DexC/DexCatch-wjl/dexmimicgen_lerobot_validation

setsid /home/dex/桌面/ICRA2027_TELEOP/.conda/envs/dex_teleop/bin/python \
  scripts/convert_rosbag_act_ready_to_lerobot.py \
  --source-root /media/dex/Cyan_data/Task_Data/task3_Data \
  --output-root /media/dex/data/lerobot_task3_screwdriver_alignment_50hz \
  --repo-id linker_a7_task3_screwdriver_alignment \
  --task screwdriver_alignment_v1 \
  --fps 50 \
  --workers 4 \
  --zstd-threads 1 \
  > /media/dex/data/imle_runtime/task3_conversion.log 2>&1 < /dev/null &
```

`--workers 4` 并行提取 4 个 rosbag；数据集写入仍按顺序进行。每个 worker 只给
zstd 一个线程，避免 4 个 worker 争抢全部 CPU。临时解压文件按批次删除，不删除
源 rosbag。

查看转换：

```bash
tail -f /media/dex/data/imle_runtime/task3_conversion.log
pgrep -af convert_rosbag_act_ready_to_lerobot.py
```

### 3.2 中断后继续

当输出目录已有部分 episode 和 `conversion_report.json` 时，使用相同参数并追加
`--resume`：

```bash
cd /home/dex/桌面/DexC/DexCatch-wjl/dexmimicgen_lerobot_validation

/home/dex/桌面/ICRA2027_TELEOP/.conda/envs/dex_teleop/bin/python \
  scripts/convert_rosbag_act_ready_to_lerobot.py \
  --source-root /media/dex/Cyan_data/Task_Data/task3_Data \
  --output-root /media/dex/data/lerobot_task3_screwdriver_alignment_50hz \
  --repo-id linker_a7_task3_screwdriver_alignment \
  --task screwdriver_alignment_v1 \
  --fps 50 --workers 4 --zstd-threads 1 --resume
```

`--resume` 跳过报告中已经成功或已经明确失败的 run。若修复了损坏的 zstd 并希望
重新转换原先的 skipped run，应使用新的空输出目录重新转换，不能依赖原报告自动
重试。

### 3.3 转换完成的判据

必须同时满足：

1. 转换进程已经退出；
2. 输出根目录存在 `conversion_report.json`；
3. 每个源 run 都出现在报告的 `episodes` 或 `skipped` 中；
4. `meta/info.json`、`meta/episodes.jsonl`、`meta/episodes_stats.jsonl` 完整；
5. 成功 episode 数、Parquet 数、帧数和元数据一致；
6. state/action 的关节名、顺序和 rad 单位有原始 rosbag 证据。

只查看、不修改元数据：

```bash
source /opt/ros/jazzy/setup.bash
python3 /home/dex/桌面/ICRA2027_TELEOP_IMLE/tools/prepare_imle_dataset.py \
  --dataset-root /media/dex/data/lerobot_task3_screwdriver_alignment_50hz \
  --source-root /media/dex/Cyan_data/Task_Data/task3_Data \
  --dry-run
```

去掉 `--dry-run` 后，工具会先备份 `meta/info.json`，再根据已验证的原始关节名写入
规范通道名和 `meta/imle_joint_mapping.json`。它不会根据“恰好是 7 维”猜测语义。

## 4. 转换完成后自动训练 IMLE

等待器会监测正式转换进程，每 30 秒检查一次，并用 PID 加进程启动时间避免 PID
复用。应先启动转换器，再启动等待器：

```bash
cd /home/dex/桌面/ICRA2027_TELEOP_IMLE

setsid bash scripts/train_imle_after_conversion.sh \
  > /media/dex/data/imle_runtime/task3_waiter_launcher.log 2>&1 < /dev/null &
```

等待器执行以下步骤：

1. 用独占文件锁防止重复启动；
2. 等待匹配 source/output 的正式转换进程退出；
3. 核对所有源记录均为成功或明确 skipped；
4. 核对 episode、Parquet、帧数、元数据和 arm7/rad 契约；
5. 建立独立 IMLE 环境，并把临时文件和 Hugging Face/Torch 缓存放到 ext4 数据卷；
6. 安装并检查 NVIDIA GPU PNG 解码器；
7. 运行一步 smoke，完成加载、前向、反向、checkpoint 保存和重载；
8. smoke 通过后，只启动一次正式训练；失败时保留日志，不无限重试。

等待器主日志：

```bash
tail -f /media/dex/data/imle_runtime/task3_imle_after_conversion.log
```

如果转换已经完成且报告存在，等待器会直接验证并启动训练。如果转换尚未启动且
报告不存在，等待器会退出，而不是无限等待一个不存在的任务。

## 5. 手动训练 IMLE

当前正式配置使用全部成功 episode，不划分验证集：

```bash
RUN=/media/dex/data/imle_checkpoints/task3_screwdriver_alignment_$(date -u +%Y%m%dT%H%M%SZ)

/media/dex/data/imle_runtime/venv/bin/python \
  /home/dex/桌面/ICRA2027_TELEOP_IMLE/tools/train_imle.py \
  --dataset-root /media/dex/data/lerobot_task3_screwdriver_alignment_50hz \
  --repo-id linker_a7_task3_screwdriver_alignment \
  --all-episodes \
  --output "$RUN" \
  --fps 50 --image-height 480 --image-width 640 \
  --epochs 100 --batch-size 16 \
  --lr 1e-4 --weight-decay 1e-6 --epsilon 0.03 \
  --seed 42 --device cuda \
  --num-workers 6 --prefetch-factor 1 \
  --tf32 --amp
```

IMLE 固定时间协议为 2 帧观测、16 步预测、执行 8 步、20 个候选。两台相机的 PNG
压缩字节由 `nvImageCodec` 在 GPU 批量解码。overlap 仍计算并记录，但偏移窗口在
`no_grad()` 下运行，不参与权重更新。

无验证模式不会生成“best”权重：

| 文件 | 保存规则 | 用途 |
| --- | --- | --- |
| `metrics.jsonl` | 每 epoch 追加 | loss、overlap、step |
| `last_training.pt` | 每 epoch 覆盖 | 模型、EMA、优化器、scheduler、RNG，可恢复 |
| `latest_deployment.pt` | 每 epoch 覆盖 | 最新 EMA 部署权重 |
| `checkpoint_epoch_010.pt` 等 | 每 10 epoch | 固定训练快照 |

从最后一个完整 epoch 恢复时，使用原输出目录：

```bash
/media/dex/data/imle_runtime/venv/bin/python \
  /home/dex/桌面/ICRA2027_TELEOP_IMLE/tools/train_imle.py \
  --dataset-root /media/dex/data/lerobot_task3_screwdriver_alignment_50hz \
  --repo-id linker_a7_task3_screwdriver_alignment --all-episodes \
  --output <原运行目录> --resume <原运行目录>/last_training.pt \
  --fps 50 --image-height 480 --image-width 640 \
  --epochs 100 --batch-size 16 --lr 1e-4 --weight-decay 1e-6 \
  --epsilon 0.03 --seed 42 --device cuda \
  --num-workers 6 --prefetch-factor 1 --tf32 --amp
```

恢复点是最后完成的 epoch；进程在某个 epoch 中途退出时，该 epoch 会重新训练。

## 6. 训练 ACT

ACT 使用同一份 7 维 LeRobot 数据。仓库中的 `scripts/train_act_v6_gpu.sh` 会读取
split；如果数据没有 `meta/splits.json`，`LEROBOT_SPLIT=train` 会使用全部 episode。

```bash
cd /home/dex/桌面/ICRA2027_TELEOP_IMLE

setsid env \
  LEROBOT_DATASET_ROOT=/media/dex/data/lerobot_task3_screwdriver_alignment_50hz \
  LEROBOT_DATASET_REPO_ID=linker_a7_task3_screwdriver_alignment \
  LEROBOT_SPLIT=train \
  ACT_OUTPUT_DIR=/media/dex/data/act_checkpoints/act_task3_screwdriver_alignment \
  ACT_CACHE_DIR=/media/dex/data/act_runtime/cache \
  ACT_EPOCHS=100 \
  ACT_BATCH_SIZE=16 \
  ACT_NUM_WORKERS=4 \
  bash scripts/train_act_v6_gpu.sh \
  > /media/dex/data/act_runtime/act_task3_train.log 2>&1 < /dev/null &
```

该入口使用 LeRobot ACT、CUDA AMP、AdamW 参数 `lr=1e-5`、
`weight_decay=1e-4`、`kl_weight=10`，默认每 20 epoch 保存一次。运行前可加入
`ACT_DRY_RUN=1`，只打印 episode、帧数、总 step、保存间隔和输出路径。

恢复 ACT 时，找到目标 checkpoint 中的 `pretrained_model/train_config.json`：

```bash
/home/dex/桌面/ICRA2027_TELEOP/.conda/envs/dex_teleop/bin/python \
  /home/dex/桌面/ICRA2027_TELEOP_IMLE/scripts/train_act_v6.py \
  --config_path=<ACT运行目录>/checkpoints/<step>/pretrained_model/train_config.json \
  --resume=true
```

恢复时继续使用原运行目录，不要把 checkpoint 复制到不支持符号链接的文件系统。

## 7. 实时查看训练

### GPU 与进程

```bash
watch -n 2 nvidia-smi
pgrep -af 'train_imle.py|train_act_v6.py'
```

### IMLE 文本指标

```bash
tail -f <IMLE运行目录>/metrics.jsonl
```

IMLE 当前每个 epoch 写一个点，因此 loss 曲线约每个 epoch 更新一次。

### TensorBoard

把 IMLE JSONL 指标同步为 TensorBoard event：

```bash
RUN=<IMLE运行目录>

setsid /media/dex/data/imle_runtime/venv/bin/python \
  /home/dex/桌面/ICRA2027_TELEOP_IMLE/tools/metrics_jsonl_to_tensorboard.py \
  --metrics "$RUN/metrics.jsonl" --log-dir "$RUN/tensorboard" \
  > "$RUN/tensorboard_sync.log" 2>&1 < /dev/null &

setsid /media/dex/data/imle_runtime/venv/bin/python -m tensorboard.main \
  --logdir "$RUN/tensorboard" --host 127.0.0.1 --port 6006 \
  > "$RUN/tensorboard_server.log" 2>&1 < /dev/null &
```

在本地工作站建立隧道：

```bash
ssh -N -L 6006:127.0.0.1:6006 dex@100.69.71.73
```

浏览器打开 `http://localhost:6006`，查看 `train/loss`、
`diagnostic/overlap_all`、`diagnostic/overlap_best` 和 `progress/epoch`。

## 8. 常见故障

### `PermissionError ... checkpoints/last`

checkpoint 所在分区不支持符号链接。把 ACT 输出迁移到 `/media/dex/data` 后重新
启动或恢复；已保存的数字 step checkpoint 通常仍然有效。

### 报告缺少源 run

转换进程可能被中断。确认它已经退出后，用完全相同的 source/output/repo/task
参数加 `--resume`。不要在报告覆盖不完整时启动训练。

### `premature end`

源 `.db3.zstd` 已截断。转换器会写入 skipped 原因并继续其他 run。若需要补回该
episode，应从采集端恢复完整文件，并输出到一个新的 LeRobot 目录重新转换。

### 系统盘空间快速减少

Hugging Face、Arrow、Torch 和临时解压缓存必须指向 `/media/dex/data`。等待脚本已
设置这些变量；手动运行时也应设置 `TMPDIR`、`HF_HOME`、
`HF_DATASETS_CACHE`、`TORCH_HOME`。

### IMLE 没有 `best_deployment.pt`

`--all-episodes` 明确关闭验证集，因此不存在可据以选择“best”的验证指标。使用
每 10 epoch 快照做离线/真机受控比较，或使用最新的 `latest_deployment.pt`。

## 9. 训练完成后的最低验收

1. checkpoint 能在 CPU 和 CUDA 上重载；
2. dataset manifest、通道名、相机顺序、50 Hz 和 rad 契约一致；
3. ACT 与 IMLE 分别做离线回放，不只看训练 loss；
4. 先 shadow，再仿真，最后做有急停和限位保护的真机受限测试；
5. 比较成功率、完成时间、关节 RMSE、动作跳变、推理延迟和接管次数；
6. 在完成部署验收前，不把新模型静默设为真机默认策略。
