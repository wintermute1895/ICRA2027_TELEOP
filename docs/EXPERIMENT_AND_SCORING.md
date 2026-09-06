# A/B data collection and trajectory scoring

## 实验原则

- A 为已验证 baseline，B 为 proposed；一次只改变一个主要因素。
- 采用被试内随机交叉设计，条件顺序使用随机化或 Latin square 平衡。
- 机器人、URDF、相机 profile、任务物体、安全阈值保持一致；无法保持的量记录为
  block/covariate。
- 练习 episode 与正式 episode 分开，不允许同一轨迹同时充当 A 和 B。
- 失败数据保留并标记 `review`，不能静默删除。

建议每名操作者每个条件先采 10 条有效 episode 做 pilot，再根据成功率差异和方差做
power analysis。正式实验优先增加操作者数量，而不是只增加同一操作者重复次数。

## 必须记录的实验元数据

`experiment_id`、`task_id`、`condition_id`、脱敏 `operator_id`、`episode_id`、随机种子、
机器人/相机 ID、Git revision、URDF/config SHA256、时间同步报告、软件环境、人工成功
标签和异常原因。

## 指标体系

所有指标保留原始值和单位。归一化总分只能用于筛选/排序，不能替代各主要指标。

| 维度 | 指标 |
|---|---|
| 任务 | success、人工介入次数、重试次数 |
| 时间 | completion time、静止等待时间 |
| 精度 | 末端 position/orientation error、装配最终误差 |
| 平滑性 | joint velocity/acceleration/jerk、tremor RMS |
| 跟踪 | command-state error、延迟、丢帧率 |
| 可执行性 | joint-limit margin、minimum singular value、collision clearance |
| 数据质量 | state/RGB/depth/TF coverage、时间戳单调性、跨 topic skew |
| 人因 | NASA-TLX 或预注册的简化主观量表 |

建议质量门：

```text
schema_pass
and timestamps_monotonic
and robot_state_coverage >= 0.99
and rgb_coverage >= 0.95
and depth_coverage >= 0.95
and no_collision_in_offline_replay
and joint_limit_margin >= configured_margin
```

质量门判断数据是否可分析，不判断任务是否成功。

`tools/score_episode_data_quality.py` is the executable form of this first
data-quality gate. It reports episode completeness, timestamp monotonicity and
gaps, state/command coverage, and camera coverage without reading a robot SDK
or changing an episode. It intentionally calls the result `data_quality_score`
rather than `A`, because condition `A` already denotes the baseline.

`tools/export_rosbag_episode.py` and `scripts/export_episode.sh` turn either a
real or simulation rosbag into the same derived per-arm `episode/v1` JSONL before this
gate. Their namespace choices are explicit rather than inferred from the bag;
the full record/export/evaluation procedure is in `docs/DATA_PIPELINE.md`.

## 统计分析

- success：混合效应 logistic model，或适合被试内设计的 McNemar/置换检验。
- time/error：线性混合效应模型；偏态明显时做预注册变换或采用置换方法。
- trajectory quality：报告中位数、IQR、bootstrap 95% CI 和 effect size。
- 多个主要指标需预先声明，必要时控制 FDR；不能事后挑选最有利指标。

## 权威参考

- ISO 9283:1998：工业机器人位姿精度、重复性和轨迹性能测试术语。
- ISO 10218-1:2025：工业机器人安全要求；软件检查不能替代现场风险评估。
- ISO/TS 15066:2016：协作机器人风险评估背景。
- Casiez et al., CHI 2012, *1 Euro Filter*，DOI: 10.1145/2207676.2208639。
- Mandlekar et al., CoRL 2021, *What Matters in Learning from Offline Human Demonstrations for Robot Manipulation*。
- Hart and Staveland, 1988；NASA-TLX 官方材料，用于操作者负担测量。

标准链接和引用细节见 `docs/REFERENCES.md`。
