# 第一阶段验收报告：DexMimicGen Can Sorting → LeRobot ACT 仿真链路

## 验收范围

只验证基础设施，不验证数据飞轮或滤波器主张：

- 一个任务：`TwoArmCanSortBlue`
- 少量 episode：3 个
- 单相机：`frontview`
- ACT 可以训练、加载、在仿真中完整 rollout
- 不出现动作维度、坐标系或控制频率错误
- 不以成功率或批量评测为验收条件

## 环境版本

| 组件 | 版本 |
| --- | --- |
| Python | 3.10.20 |
| PyTorch | 2.6.0+cu126 |
| torchvision | 0.21.0+cu126 |
| DexMimicGen | 0.1.0 |
| Robosuite | 1.5.0 |
| Robomimic | 0.3.0 |
| LeRobot | 0.3.2 |
| MuJoCo | 3.3.6 |
| mink | 1.0.0 |
| numpy | 1.23.3 |
| numba | 0.56.4 |
| h5py | 3.12.1 |
| scipy | 1.11.4 |

Conda 环境：`/home/pao/miniconda3/envs/dex_teleop`

## 1. Robomimic HDF5 数据校验

源文件：

`data/two_arm_can_sort_random.hdf5`

校验结果：

- episode 数量：1020
- 总帧数：322073
- 单 episode 长度范围：276～349
- action 维度：24
- state 维度：112
- 单相机图像：`frontview`，`84x84x3 uint8`
- action 全部有限值
- source `data.attrs["total"]` 与各 episode 帧数求和一致：322073

## 2. Robomimic HDF5 → LeRobot 转换

转换脚本：

`scripts/convert_robomimic_to_lerobot.py`

输出数据集：

`lerobot_data/dexmimicgen_can_sort_subset_clean/`

转换摘要：

| 项目 | 值 |
| --- | --- |
| episode 数 | 3 |
| 总帧数 | 834 |
| fps | 20 |
| observation.state | 14 维 float32 |
| action | 24 维 float32 |
| 相机 | `observation.images.frontview`，84×84×3 |
| robot_type | `robomimic` |

校验通过项：

- episode 数量一致：3
- 长度一致：276、282、276
- 图像、状态、动作 shape 正确
- action 与 state 全为有限值
- 时间戳单调递增
- 时间步长：约 0.05s，即 20Hz

## 3. 最小 ACT 训练

训练命令：

```bash
python -m lerobot.scripts.train \
  --policy.type=act \
  --dataset.repo_id=dexmimicgen_two_arm_can_sort_subset \
  --dataset.root=lerobot_data/dexmimicgen_can_sort_subset_clean \
  --dataset.video_backend=pyav \
  --policy.device=cpu \
  --policy.pretrained_backbone_weights=null \
  --batch_size=2 \
  --steps=20 \
  --save_checkpoint=true \
  --eval_freq=0 \
  --output_dir=outputs/act_smoke_v4
```

结果：

- 训练 20 步完成
- checkpoint 保存于：
  `outputs/act_smoke_v4/checkpoints/000020/pretrained_model`
- policy 可加载，`select_action` 输出 shape 为 `(1, 24)`

## 4. ACT output → Robosuite controller action 适配

适配脚本：

`scripts/rollout_act_robosuite.py`

动作适配原则：

- 不 reshape、不 permute。
- policy 输出的 24 维 action 直接按原顺序送入 `env.step(action)`。
- 仅执行 `np.clip(action, env.action_spec[0], env.action_spec[1])`。

数据集中 raw action 的 24 维顺序已核对为：

1. `right_abs_pos`：3 维
2. `right_abs_rot_axis_angle`：3 维
3. `left_abs_pos`：3 维
4. `left_abs_rot_axis_angle`：3 维
5. `left_gripper`：6 维
6. `right_gripper`：6 维

合计：24 维。

## 5. 坐标系与控制频率

坐标系：

- 直接从 HDF5 的 `env_args.env_kwargs.controller_configs` 构造环境。
- controller：`WHOLE_BODY_MINK_IK`
- `ik_input_ref_frame`: `world`
- `ik_input_rotation_repr`: `axis_angle`
- `ref_name`: `gripper0_right_grip_site`, `gripper0_left_grip_site`

因此 rollout 环境与数据采集环境使用同一套控制器参数和坐标系定义，没有使用默认 controller 替代。

控制频率：

- 环境 `control_freq=20`
- LeRobot dataset `fps=20`
- rollout 每步 timestamp = step / 20.0
- rollout 日志中相邻 timestamp 差为约 0.05s

## 6. 完整仿真 rollout

输出目录：

`outputs/rollout_smoke_v2/`

结果：

- 实际执行步数：300
- 视频：`rollout.mp4`
- 日志：`rollout_log.jsonl`
- 摘要：`rollout_summary.json`
- action 维度始终为 24
- observation state 维度始终为 14
- action 全为有限值
- 无维度、坐标系或控制频率异常

## 结论

第一阶段验收条件已满足：

- [x] 单任务、少量 episode、单相机
- [x] ACT 可训练
- [x] checkpoint 可加载
- [x] 仿真中完整 rollout
- [x] 无动作维度错误
- [x] 无坐标系错误
- [x] 无控制频率错误
- [x] 不以成功率或批量评测作为验收条件
