# Legacy 数据利用计划

数据源：`/media/ilex/Cyan_data/data`。当前盘上约 427 GiB，包含 GELLO、FSM、VIST、
One-Euro Filter 和 `data_analyze` 五类资产。它们不能直接合并成新的 A/B 数据集，
必须先经过 provenance、语义和标签审计。

## 已确认价值

VIST 样本的元数据和 ROS bag 记录包含：

- LinkerTA/外骨骼原始与滤波关节控制；
- 机器人 joint state、pose state 和控制指令；
- RealSense RGB-D 与 camera info；
- Linker Hand L10 状态/控制；
- VIST performance、intent factors 和 filter performance；
- 每个 episode 的 rosbag duration、起始时间、消息数和 topic 计数。

`data_analyze` 另有结构化 `telemetry.npz`，抽样显示包含 timestamps、qpos、qvel、effort、
actions、同步检查字段和多指触觉矩阵。这部分可能比 ROS bag 更适合直接做统一数组数据集，
但机械臂/手的语义仍需核对。

## 三层用途

### L0：历史诊断与 replay

立即可用。重算延迟、频率、One-Euro 平滑性、控制跟踪误差，挖掘困难片段，复现旧 VIST/FSM
行为。结果只标记为 `legacy_replay`。

### L1：表示预训练或 warm start

可尝试用来学习动作/视觉表示或初始化 residual policy，但必须按 session/操作者/日期分组切分，
不能按帧随机切分。所有训练 manifest 记录旧设备、旧 URDF、旧相机位置、关节顺序和单位。

### L2：正式 A/B 证据

默认禁止。只有在逐 episode 确认任务、condition、success/failure、参考轨迹、扰动参数、
安全配置和当前 episode contract 语义一致后，才可以纳入正式统计。

## 推荐顺序

1. 运行 `audit_legacy_dataset.py`，得到组和 episode 注册表。
2. VIST 可先用 `export_legacy_vist_episode.py` 导出为当前 JSONL，随后进入质量门、轨迹评分和
   hard-case mining。它将 `filtered_left_joint_control` 明确标为命令 proxy；当前已验证的
   `legacy_vist_left` profile 会执行 degrees-to-radians，并对第 4、6 关节取反。该 profile
   只能用于同一历史控制器版本，必须逐协议复核。
   单条 replay 可通过 `scripts/run_legacy_vist_flywheel.sh EPISODE_DIR OUTPUT_DIR` 运行。它使用
   `legacy_vist_rgb_only_quality_gate.yaml`，因此深度缺失不会阻止历史分析；该豁免不能用于新数据。
3. 选 VIST、GELLO、FSM、One-Euro 各 3 条样本，读取 topic schema 和数组形状，确认单位、
   joint order、时间戳来源和 command/state 关系。
4. 生成 `legacy_episode_manifest.jsonl`，每条数据带 source group、protocol version、
   provenance、可用信号和 eligibility。
5. 只对 L0 数据运行现有 trajectory quality / hard-case mining；保留失败数据。
6. 用历史数据定义扰动覆盖和 replay 优先级，再采新数据完成冻结后的 A/B。

## 当前学术判断

这批数据最适合回答两个问题：

1. 历史遥操作链路中哪些信号能可靠预测困难/恢复片段？
2. 在相同数据预算下，参考条件化的 residual 学习是否比直接学习整条动作更有效？

它不适合直接证明新方法在当前硬件上的最终成功率，因为旧数据的任务、相机、机器人模型和
控制语义可能已经发生变化。
