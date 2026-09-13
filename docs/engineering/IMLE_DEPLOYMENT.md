# IMLE 真机部署（Linux）

IMLE 的上线方式和仓库里的 ACT 一样：GPU worker 与 ROS adapter 分开，只发布 candidate；`model_deployment_supervisor` 才是进桥接层的唯一边界。模型进程不碰 SDK、不碰 `lbot_driver`。

```text
LinkerTA raw ────────────────┐
IMLE candidate ──> model_deployment_supervisor ──> teleop_control_bridge ─> lbot_driver
                         |                         (mapping, limits, armed gate)
                         └─ diagnostics / fallback
```

当前 Task2 权重是 **7 维右臂绝对关节目标**，训练数据直接来自 ROS `JointState.position`（LinkerTA **角度制**），50 Hz，双 RGB 相机 480×640。不要用 ACT 的 radians 合同去加载这份 checkpoint。

## 1. Linux 环境

在机器人或同网 Linux 主机上准备：

| 依赖 | 说明 |
| --- | --- |
| ROS 2 Humble 或 Jazzy | adapter / supervisor 走系统 Python |
| CUDA + 含 torch 的训练环境 | worker 用，不要塞进 ROS dist-packages |
| `ICRA2027_TELEOP` | 本仓库，含部署脚本 |
| `ICRA2027_TELEOP_IMLE` | 训练代码，必须有 `src/robot_policy_imle` |
| `latest_deployment.pt` | 训练导出的部署权重（不要用带优化器的 `last_training.pt`） |

训练环境可以是 `teleop-train` / `dex_teleop`，也可以是 IMLE 自己的 venv。启动前指定：

```bash
export IMLE_ROOT=/home/dex/桌面/ICRA2027_TELEOP_IMLE
export IMLE_ENV_PREFIX=/media/dex/cx_Data/imle/task2_power_button_press/runtime/venv
# 若未设置 IMLE_ENV_PREFIX，脚本会回退到 teleop-train / teleop
```

SJ01 上已训完的 Task2 部署权重：

```text
/media/dex/cx_Data/imle/task2_power_button_press/checkpoints/task2_power_button_press_20260911T153358Z/latest_deployment.pt
```

## 2. 晋级 runtime 配置

不要改共享的 `config/runtime/imle.yaml`。从 checkpoint 生成一份带 SHA-256 的新文件：

```bash
cd /path/to/ICRA2027_TELEOP

bash scripts/promote_model_checkpoint.sh --kind imle \
  --checkpoint /media/dex/cx_Data/imle/task2_power_button_press/checkpoints/task2_power_button_press_20260911T153358Z/latest_deployment.pt \
  --imle-root /home/dex/桌面/ICRA2027_TELEOP_IMLE \
  --output /tmp/imle-task2-promoted.yaml
```

输出里会写入 `enabled: true`、checkpoint 路径和 `checkpoint_sha256`。也可以把 `config/runtime/imle-task2.yaml` 当作模板，用 `--template` 指向它。

## 3. 校验（不上电、不加载 CUDA）

```bash
bash scripts/validate_imle_deployment.sh /tmp/imle-task2-promoted.yaml
```

通过时应打印 `[READY]`、checkpoint SHA-256 和 `imle_root`。hash 对不上、`enabled: false`、缺 `src/robot_policy_imle` 都会直接失败。

## 4. 只起 candidate（shadow 前的冒烟）

这一步只发布 `/imle/right_arm_joint_control`，**不会**接管机械臂：

```bash
bash scripts/start_imle_adapter.sh /tmp/imle-task2-promoted.yaml
```

日志里应出现 `[READY] IMLE worker: /tmp/teleop_imle.sock`。另开终端：

```bash
ros2 topic hz /imle/right_arm_joint_control
ros2 topic echo /imle/right/diagnostics --once
```

`ready: false` 且 `reason=input_missing_or_stale` 表示相机或关节状态还没到。需要双相机 `main_rgb` / `auxiliary_rgb` 和 `/robot1/right_arm/joint_states`。

## 5. Shadow 部署（默认、安全）

Shadow 下 supervisor **永远转发 LinkerTA raw**，同时记录是否接受 IMLE candidate：

```bash
bash scripts/start_model_deployment.sh config/runtime/model_deployment.yaml \
  --source=imle --imle-config=/tmp/imle-task2-promoted.yaml --shadow
```

诊断在 `/model_deployment/diagnostics`。此时桥接层仍走遥操；用来确认推理频率、维度和超时，不用于评任务成败。

完整硬件图（相机 + worker/adapter + supervisor + 驱动 + 桥）用 rollout 入口：

```bash
bash scripts/start_model_rollout.sh --config config/runtime/rollout.yaml \
  --source imle --imle-config /tmp/imle-task2-promoted.yaml --shadow \
  --record-dir /media/ilex/Cyan_data/ICRA2027_TELEOP_DATA/rollouts/imle-$(date -u +%Y%m%dT%H%M%SZ)
```

Ctrl-C 停止。随后可做只读评测：

```bash
bash scripts/evaluate_model_rollout.sh \
  --bag /media/ilex/Cyan_data/ICRA2027_TELEOP_DATA/rollouts/<timestamp>
```

评测不是任务成功授权，也不会解除 armed gate。

## 6. Active（必须显式确认）

IMLE 和 ACT 一样输出绝对关节目标，不要用 residual 的 `max_delta_rad: 0.05` 去晋级。用带绝对位姿窗口的配置，例如 `config/runtime/model_deployment_active_test.yaml`。

```bash
bash scripts/start_model_deployment.sh config/runtime/model_deployment_active_test.yaml \
  --source=imle --imle-config=/tmp/imle-task2-promoted.yaml \
  --active --confirm=I_UNDERSTAND_MODEL_DEPLOYMENT
```

真机 armed rollout 还要额外确认，且必须物理急停就位：

```bash
bash scripts/start_model_rollout.sh --config config/runtime/rollout.yaml \
  --source imle --imle-config /tmp/imle-task2-promoted.yaml \
  --active --real --physical-estop-ready \
  --confirm=I_UNDERSTAND_REAL_ROLLOUT \
  --model-confirm=I_UNDERSTAND_MODEL_DEPLOYMENT
```

这些命令**不会**自动 arm 手部 CAN。手控仍是独立、显式 armed 的流程。

## 7. 推理合同（必须与训练一致）

Worker 每个控制周期返回 **一步** 7D 命令（字段名仍为 `command_rad`，数值是 **度**，adapter 按 `action_units: degrees` 原样发到 ROS）：

1. 维护 `obs_horizon=2` 的状态/图像窗口；首帧不足时复制当前帧。
2. 队列空时一次生成 `candidate_count=20` 条 `pred_horizon=16` 轨迹。
3. 第一次规划随机选候选；之后用 overlap：上一条轨迹的 `8:16` 对当前候选的 `0:8`。
4. 只执行选中轨迹的前 `action_horizon=8` 步，然后重新规划。
5. 超时、缺帧、推理异常会清空窗口和队列，不会接着用旧 chunk。

默认 `inference_hz: 50.0`，与 Task2 训练 FPS 一致。相机约 15 Hz 时，adapter 会复用尚未超时的最新帧（`input_timeout_ms` 默认 2000）。

## 8. 和 ACT 脚本的对应关系

| ACT | IMLE |
| --- | --- |
| `scripts/validate_act_deployment.sh` | `scripts/validate_imle_deployment.sh` |
| `scripts/start_act_adapter.sh` | `scripts/start_imle_adapter.sh` |
| `tools/act_worker.py` | `tools/imle_worker.py` |
| `tools/act_ros_adapter.py` | `tools/imle_ros_adapter.py` |
| `config/runtime/act-button-A.yaml` | `config/runtime/imle-task2.yaml` |
| `/act/right_arm_joint_control` | `/imle/right_arm_joint_control` |

统一入口仍是 `scripts/start_model_deployment.sh` 和 `scripts/start_model_rollout.sh`，把 `--source=act --act-config=...` 换成 `--source=imle --imle-config=...`。

## 9. 常见失败

| 现象 | 处理 |
| --- | --- |
| `IMLE runtime is disabled` | 先 promote，不要直接启用共享 YAML |
| `checkpoint_sha256 mismatch` | 权重被覆盖或拷错；重新 promote |
| `IMLE source not found` | 设置 `IMLE_ROOT` / `imle_root` |
| `IMLE Python env is unavailable` | 设置 `IMLE_ENV_PREFIX` 指向含 torch 的环境 |
| worker READY 但 candidate 为 0 | 双相机或关节状态缺失/超时，看 `/imle/right/diagnostics` |
| active 被 `candidate_delta_exceeded` 打回 | 不要用 residual 窗口；用 `imle_max_delta_rad` / active test 配置 |
| 动作方向或幅度完全不对 | 确认没有把 IMLE 当 radians ACT 来发；Task2 是角度制 |

共享边界说明见 `docs/engineering/MODEL_DEPLOYMENT.md`。
