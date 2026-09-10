# ACT 模型真机部署测试记录

> 本文记录 ACT 部署准备环节的实操过程与遇到的问题(由 AI 直接执行,人复核)。
> 部署指令集见个人笔记 `~/Desktop/knowledge/ICRA2027/ACT模型部署_v2.md`;轮换记录见 `docs/3个task_act的实验记录.md`。

## 测试对象

| 项 | 内容 |
|---|---|
| 模型 | Task2 电源按钮 ACT,`task2_button_press_50hz_20260908T171908Z`,step 466900(100 epochs 完成) |
| 训练数据来源 | Dex 服务器,98 个 50Hz episode(lerobot v2.1,`lerobot_task2_button_press_50hz`) |
| 存放位置 | `/media/fanshihao/robot_data/ICRA2027_Data/act_checkpoints/.../checkpoints/466900/pretrained_model` |
| promoted yaml | `config/runtime/act-task2-50hz.yaml`(SHA-256 `8ed6d32a...`) |
| 日期 | 2026-09-09 |

## 执行过程与结果

六步流水线走到 ③,等待真机:

| 步骤 | 结果 | 说明 |
|---|---|---|
| ① promote | ✅ | 生成 `act-task2-50hz.yaml`,`last` 自动解析为 step 466900 |
| ② validate | ✅ | `validate_act_deployment.sh` 通过,checkpoint + SHA-256 + stats 一致 |
| ③ 冒烟 | ✅ | worker 3.0s 加载模型 → `[READY]`;adapter 正确上报缺输入(无真机时的保护行为) |
| ④ 真机 active | ⏸ 待硬件 | 机械臂/双相机/E-stop 就绪后执行,命令见 v2 笔记 |
| ⑤ bag 评估 | — | |

同日复测旧模型 `models/act_button_A`(对照组):validate ✅、冒烟 ✅(5.1s READY),同样可部署。

## 遇到的问题与解决

### 问题 1:新数据集缺少部署必需的 dataset stats.json

**现象**:promote ACT 模型强制要求 `--dataset-stats`,但新 lerobot 数据集的 `meta/` 下只有 `episodes_stats.jsonl`(逐 episode 统计),没有数据集级的 `stats.json`。

**根因**:转换管线(lerobot v2.1)写出了逐 episode 统计,但没有做全数据集聚合。

**解决**:用本机 teleop 环境的 `lerobot.datasets.compute_stats.aggregate_stats` 聚合 98 个 episode 的统计,写回 `meta/stats.json`。两个坑:
1. `episodes_stats.jsonl` 里的统计值是 list,需先转 `np.ndarray`(lerobot 0.4.4 的 `_assert_type_and_shape` 强校验);
2. 聚合函数在本机 lerobot 0.4.4 位于 `lerobot.datasets.compute_stats`,旧路径 `lerobot.common.datasets.utils` 已不存在(lerobot 版本间 API 迁移)。

**验证**:stats 键完整(`observation.state`/`action` 等 mean 形状 (7,)),validate 通过。

**后续建议**:把"转换后聚合 stats"加进 `convert_episode_to_lerobot.sh` 的收尾步骤,避免每个数据集手工补。

### 问题 2:数据盘漂移(第三次遇到)

**现象**:查找模型时发现 `Cyan_data` 未挂载,新数据和新模型实际在今天挂载的 `robot_data` 盘上(`/media/fanshihao/robot_data`)。

**影响**:promoted yaml 里的 checkpoint/stats 路径写死 `robot_data` 挂载点,**真机部署前必须确认该盘挂载在同一位置**;换盘/换挂载点后需要重新 promote 或改 yaml 路径。

**教训**:这已经是第三次盘漂移(Seagate → Cyan → robot_data)。部署前检查单里固定一条:"确认 yaml 里的路径指向当前实际挂载点"。

**根治(2026-09-09 已实施)**:yaml 改用 `${TELEOP_DATA_ROOT}` 占位符 + `scripts/resolve_data_disk.sh` 启动时按优先级自动探测挂载盘(robot_data > Cyan_data > Seagate Hub),换盘零改动。详见个人笔记「针对挂载盘数据管理」。

### 问题 3(流程级):部署边界收敛到 active

**背景**:ACT 是开环推理,不接真机时模型看不到自己动作的后果;离线候选输出不构成性能验收。

**决定**(2026-09-09,团队通知):ACT 与 filter 的部署边界只有 active;验证链路为「冒烟(worker READY)确认软件就绪 → 显式人工安全确认 → 真机 active」。

**执行**:仓库与知识库全部文档同步(README、部署笔记、实验记录、流程笔记),删除 filter 专用采集配置 `config/capture_session_task{1,2,3}_filter.env`;部署代码删除非 active 模式,避免接手人误用旧流程。

## 冒烟测试原始输出(2026-09-09,新模型)

```text
Loading weights from local directory
[ACT] model loaded in 3.0s; inference ready
[READY] ACT worker: /tmp/teleop_act.sock
[INFO] [act_ros_adapter]: [diag] infer skipped missing=['state', 'observation.images.main_rgb', 'observation.images.auxiliary_rgb'] stale_ages_s={}
```

解读:`missing` 三项 = 机械臂状态 + 两路相机,均属"未接真机"的正常保护行为;软件链路(配置校验 → 环境解析 → 模型加载 → socket → adapter → 输入完整性检查)全通。

### 问题 4(2026-09-09 真机首跑):ROS_LOG_DIR 挂载点写死导致 deployment 启动即挂

**现象**:rollout 各组件正常(双相机 READY、rosbag 开录),随后 `RuntimeError: rollout process exited: [('model_deployment', 1)]` 整体停机。

**根因**:`/tmp/teleop_rollout_logs/model_deployment.log` 显示 `mkdir: 无法创建目录 "/media/fanshihao/Cyan_data": 权限不够`——前一天为防 ROS 日志写系统盘,把 `ROS_LOG_DIR` 默认值写死到 Cyan_data;当天该盘未挂载,`mkdir -p` 在 root 拥有的 `/media/fanshihao/` 下失败,`set -e` 直接退出。这是「问题 2 盘漂移」的连锁反应。

**解决**:`scripts/start_model_deployment.sh` 与 `start_learned_filter.sh` 改为候选目录依次回退(`Cyan_data → robot_data → /tmp/teleop_ros_logs`),选第一个可创建的;`ROS_LOG_DIR` 环境变量仍可强制指定。已验证自动选中 robot_data。

## 真机执行指令(单行可复制)

> 多行 `\` 续行粘贴容易截断报错,统一用单行。

新模型(task2-50hz):

```bash
bash scripts/start_model_rollout.sh --config config/runtime/rollout_active_test.yaml --source act --act-config config/runtime/act-task2-50hz.yaml --real --physical-estop-ready --confirm=I_UNDERSTAND_REAL_ROLLOUT --model-confirm=I_UNDERSTAND_MODEL_DEPLOYMENT --record-dir "/media/fanshihao/robot_data/ICRA2027_Data/act_rollouts/task2/50hz_real_v1"
```

旧模型对照(button_A,可选):

```bash
bash scripts/start_model_rollout.sh --config config/runtime/rollout_active_test.yaml --source act --act-config config/runtime/act-button-A.yaml --real --physical-estop-ready --confirm=I_UNDERSTAND_REAL_ROLLOUT --model-confirm=I_UNDERSTAND_MODEL_DEPLOYMENT --record-dir "/media/fanshihao/robot_data/ICRA2027_Data/act_rollouts/task2/buttonA_real_v1"
```

停止:Ctrl+C。评估:

```bash
bash scripts/evaluate_model_rollout.sh --bag "/media/fanshihao/robot_data/ICRA2027_Data/act_rollouts/task2/50hz_real_v1"
```

## 真机前检查单(④ 执行前逐项确认)

1. `robot_data` 盘挂载在 `/media/fanshihao/robot_data`(promoted yaml 路径依赖)
2. 机械臂上电、主臂 CAN 启用(`sudo bash scripts/enable_all_can.sh --confirm ENABLE_ALL_CAN_INTERFACES`)
3. 双相机出帧:`ros2 topic hz /camera/camera/color/image_raw` 与 `/camera2/...`
4. 物理 E-stop 就位,有人在场
5. 命令:`start_model_rollout.sh --config config/runtime/rollout_active_test.yaml --source act --act-config config/runtime/act-task2-50hz.yaml --real --physical-estop-ready --confirm=I_UNDERSTAND_REAL_ROLLOUT --model-confirm=I_UNDERSTAND_MODEL_DEPLOYMENT --record-dir /media/fanshihao/robot_data/ICRA2027_Data/act_rollouts/task2/50hz_real_v1`

## 遗留风险

- 频率链未闭环:相机 15Hz / ACT 10Hz / 机械臂 50Hz(见 `~/Desktop/knowledge/ICRA2027/数采+act+推理问题.md`),旧模型真机效果差疑与此有关;新模型(50Hz 数据训练)是否改善待真机验证。
- 新模型训练集含 09-08 新采的 episode,与旧 button_A 的数据分布有差异,真机表现不可直接类比。

当前 v2 快捷命令:

```bash
bash scripts/run_act_task2_real.sh v2
```
