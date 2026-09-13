# Filter 模型选择与部署采集进度

> 日期：2026-09-11
> 当前 task：Task2 `power_button_press_v1`
> 当前目标：从 Task2 filter 候选中选出一个模型，部署到遥操作采集链路，再采集新的含 filter 数据。
> 分支状态：当前在 `fsh/humble`；实验代码来自
> `origin/exp/continuous-filter-backbone-spike = 841f132`。
> 当前代码和模型修改尚未提交。

---

## 1. 当前结论

Task2 的 6 个归档 checkpoint 已经能够被当前代码加载和推理。

但是，这 6 个模型目前仍然是 **action-reference 模型**，不是可以产生非零辅助量的完整
continuous-gain filter：

```text
authority_mode = zero
gain_enabled = false
无 gain_head
alpha 恒为 0
```

因此当前状态是：

```text
模型可加载
模型可做离线动作预测
worker 可运行并保持 control-neutral
尚不能作为 active filter 修改机械臂命令
```

要完成“选择一个 filter 部署并采集新数据”，后续必须选择以下路线之一：

1. 将 Task2 归档模型作为 fixed-gain action filter 进行受控选型；
2. 重新训练带 gain head、`authority_mode=rate_limited` 的 Task2 filter。

---

## 2. 已完成的工作

### 2.1 已拉取模型和实验证据

从 `841f132` 导出：

```text
artifacts/filter_reference_20260910/
├── README.md
├── CHECKSUMS.sha256
├── evidence_freeze.json
└── checkpoints/
    ├── button/
    └── screwdriver/
```

Task2 模型路径：

```text
artifacts/filter_reference_20260910/checkpoints/button/
├── cvae_seed7.pt
├── cvae_seed17.pt
├── cvae_seed27.pt
├── deterministic_seed7.pt
├── deterministic_seed17.pt
└── deterministic_seed27.pt
```

校验结果：

```text
12/12 checkpoint SHA-256 校验成功
```

Task2 实验指标位于：

```text
artifacts/filter_reference_20260910/evidence_freeze.json
```

### 2.2 已接入实验分支 filter 核心代码

当前工作区已更新以下核心文件：

- `src/teleop_filter/trajectory_vae.py`
- `src/teleop_filter/runtime.py`
- `src/teleop_filter/training_config.py`
- `src/teleop_filter/safety.py`
- `src/teleop_filter/__init__.py`
- `tools/train_trajectory_filter.py`
- `tools/evaluate_trajectory_filter.py`
- `tools/learned_filter_worker.py`
- `tools/learned_filter_ros_adapter.py`
- `tools/promote_runtime_model.py`
- `tools/run_filter_ablations.py`
- `config/filters/trajectory_cvae_transformer_v0_1.yaml`
- `config/filters/trajectory_cvae_transformer_v0_2_vlm.yaml`
- `config/runtime/learned_filter.yaml`
- `config/runtime/learned_filter_task2_local.yaml`

### 2.3 已解决的兼容问题

#### 问题 A：checkpoint 配置字段不兼容

现象：

```text
TypeError: TrajectoryFilterConfig.__init__() got an unexpected keyword argument
'zero_initialize_action_head'
```

原因：

- 归档训练代码比分支源码多写入了 `zero_initialize_action_head`；
- 该字段用于记录训练时是否零初始化动作头；
- 它不在 state dict 中，不影响推理参数。

处理：

- `TrajectoryFilterConfig` 增加该 inference-neutral 字段；
- 保留原始 checkpoint metadata，不再报错。

#### 问题 B：target semantics 不兼容

归档模型：

```text
target_semantics = delta_from_last_executed
```

原分支 runtime 只接受：

```text
residual
synthetic_smoke_residual
recorded_expert_action
```

处理：

- runtime 增加 `delta_from_last_executed`；
- 该语义下 `predicted_actions` 就是相对上一次执行动作的 delta；
- `predicted_residuals` 直接复用该 delta。

#### 问题 C：worker residual 组合错误

原 worker 按绝对专家动作处理：

```python
proposed_residual = (predicted_action - baseline) * authority
```

对于 `delta_from_last_executed` 模型，这会错误地把 delta 再减 baseline。

处理：

- worker 改为使用 `prediction.predicted_residuals`；
- 不再对 delta 二次组合；
- open-loop chunk 缓存也改为缓存 residual。

#### 问题 D：authority fallback 语义不清晰

原逻辑：

```python
authority = alpha if gain_enabled else gate
```

归档模型 `gain_enabled=false`、`alpha=0`、没有 gate，会导致错误地使用 `gate=1`。

处理：

```text
有 alpha -> 使用 alpha
无 alpha，有 legacy gate -> 使用 gate
两者都没有 -> authority = 0
```

这保证没有明确 authority 的 checkpoint 不会静默接管控制。

#### 问题 E：Task2 runtime 安全字段缺失

处理：

- Task2 runtime 增加：
  - joint min/max；
  - max residual；
  - residual rate；
  - command velocity；
  - model age；
  - fallback 相关配置；
- worker 使用独立 `SafetyProjector`。

### 2.4 已保留的本地能力

接入实验代码时保留：

- `paths_env.expand_config_paths()`；
- `${TELEOP_DATA_ROOT}` 路径展开；
- adapter 推理日志节流；
- 本地 Task2 topic、相机和 SigLIP2 cache 路径；
- 当前部署 supervisor 和 bridge 边界。

---

## 3. 当前验证结果

### 3.1 模型加载和推理

新增测试：

```text
tools/tests/test_reference_filter_compatibility.py
```

验证内容：

- 12 个归档 checkpoint 全部可加载；
- 动作输出 shape 为 `(1, 8, 7)`；
- 输出全部为 finite；
- Task2 归档模型 `alpha=0`。

执行：

```bash
PYTHONPATH=src /home/fanshihao/miniforge3/envs/teleop/bin/python \
  -m unittest tools.tests.test_reference_filter_compatibility -v
```

结果：

```text
2 tests passed
```

### 3.2 Filter 回归测试

执行：

```bash
PYTHONPATH=src /home/fanshihao/miniforge3/envs/teleop/bin/python -m unittest \
  tools.tests.test_trajectory_cvae \
  tools.tests.test_filter_training_config \
  tools.tests.test_residual_training_contract \
  tools.tests.test_safety_projector \
  tools.tests.test_reference_filter_compatibility -v
```

结果：

```text
26 tests passed
```

### 3.3 Task2 worker control-neutral 验证

使用 `button/cvae_seed7.pt` 和 mock VLM encoder 验证：

```text
alpha = 0.0
residual = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
command = raw command
```

说明 compatibility layer 没有把未授权的 action prediction 直接接到控制路径。

### 3.4 全量测试

执行：

```bash
PYTHONPATH=src /home/fanshihao/miniforge3/envs/teleop/bin/python \
  -m unittest discover -s tools/tests -p 'test_*.py' -v
```

结果：

```text
124 tests
122 passed
2 failed
1 skipped
```

两个失败与本次 filter 无关：

1. 手部 gesture cycle 配置与旧测试期望不一致；
2. vendored hand SDK 缺少 `python-can`。

---

## 4. Task2 模型离线对比

按 evidence manifest 中的聚合 MAE 排序：

| 模型 | MAE | RMSE | First-step MAE |
|---|---:|---:|---:|
| cvae seed7 | 0.006583 | 0.014684 | 0.004148 |
| cvae seed17 | 0.006599 | 0.014708 | 0.004162 |
| cvae seed27 | 0.006690 | 0.014784 | 0.004235 |
| deterministic seed17 | 0.008043 | 0.014633 | 0.005101 |
| deterministic seed7 | 0.008153 | 0.015258 | 0.005072 |
| deterministic seed27 | 0.009014 | 0.015613 | 0.005735 |

初步候选：

```text
主候选：button/cvae_seed7.pt
对照：button/deterministic_seed17.pt
```

注意：

- `cvae_seed7` 的 MAE 和 first-step MAE 最好；
- `deterministic_seed17` 的 RMSE 略低；
- 两者都不能仅凭这些离线指标证明在真机遥操中更“丝滑”；
- 必须继续比较 latency、jerk、接管次数、修正次数和任务成功率。

---

## 5. 当前阻塞问题

### 阻塞 1：归档模型没有 gain head

当前 6 个 Task2 checkpoint：

```text
authority_mode = zero
gain_enabled = false
state_dict 中没有 gain_head
```

因此无法直接验证：

- rate-limited continuous gain；
- fixed gain；
- framewise gain；
- risk-conditioned authority；
- 辅助强度和操作员接管之间的关系。

如果直接把 `gain_enabled=true` 打开，模型没有训练过的 gain 参数，不能得到有效结果。

### 阻塞 2：真机 active 路线尚未确定

可选方案：

#### 方案 A：fixed-gain action filter

- 复用当前 action prediction；
- 增加 runner/config 层的固定 authority；
- 在真机上比较不同固定 alpha；
- 优点：不需要重训，能较快完成 Task2 选型；
- 缺点：不是论文主架构的完整 continuous-gain filter。

#### 方案 B：重新训练 gain-enabled filter

- 使用新的 Task2 数据重新训练；
- checkpoint 包含 action head 和 gain head；
- 可以测试 full/rate-limited/framewise/fixed 等 ablation；
- 优点：与论文主方法一致；
- 缺点：需要 preparing、训练、评估和 promote 全流程。

### 阻塞 3：真实 SigLIP2 E2E 尚未在本轮验证

本次沙箱运行中可移动数据盘未保持挂载，因此无法加载：

```text
/media/fanshihao/Seagate Hub/ICRA2027_DATA_TASK2/vlm_cache
```

模型本体和 worker composition 已用 mock encoder 验证，但真实 SigLIP2 推理仍需要：

- 数据盘保持挂载；
- cache revision
  `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2` 可读；
- 两台相机按 `[main_rgb, auxiliary_rgb]` 顺序在线。

### 阻塞 4：没有真实设备和真实 latency

当前遥操设备未连接，尚未验证：

- master 主臂输入；
- 机械臂 joint state；
- LinkerTA topic；
- CAN；
- 5 Hz worker 与相机 15 Hz 的实际延迟；
- worker timeout、fallback 和 SafetyProjector 的实际行为。

### 阻塞 5：尚无 promoted Task2 runtime

本轮只完成了 checkpoint 兼容和离线验证，没有为
`cvae_seed7.pt` 或 `deterministic_seed17.pt` 创建正式 promoted runtime YAML。

promoted runtime 必须固定：

- checkpoint 绝对路径；
- checkpoint SHA-256；
- SigLIP2 cache；
- 相机顺序；
- topic；
- safety 参数；
- inference/execution 模式。

### 阻塞 6：新采集数据的 provenance 尚未完整接入

实验分支中的 assisted-round provenance 仍需要完整合入：

- `collection_round`
- `control_mode`
- `filter_checkpoint`
- raw command
- filter output
- executed assisted action

如果不完成这些字段，后续无法判断 ACT 学到的是人类意图、filter 输出还是最终执行动作。

---

## 6. 下一步执行顺序

### 第一步：确定 Task2 选型路线

必须先决定：

```text
fixed-gain action filter
```

还是：

```text
重新训练 gain-enabled filter
```

在这项决定完成前，不应该把当前 6 个归档模型直接接到 active 真机控制。

### 第二步：离线筛选 Task2

比较 6 个 button 模型：

- `cvae_seed7/17/27`
- `deterministic_seed7/17/27`

至少输出：

- MAE/RMSE/first-step；
- 预测误差分布；
- 每个关节的误差；
- action chunk 连续性；
- inference latency；
- seed 间差异。

### 第三步：生成候选 runtime

对通过离线筛选的模型生成独立 YAML：

```text
config/runtime/filter-task2-cvae-seed7.yaml
config/runtime/filter-task2-deterministic-seed17.yaml
```

不要覆盖已有 runtime 配置。

### 第四步：Shadow 测试

设备接上后：

- 模型只预测；
- 不允许改变机械臂；
- 验证 camera order、SigLIP2、state 和 latency；
- 记录 raw command、predicted residual、alpha 和 diagnostics。

### 第五步：低权限 active

在实现 authority 后：

```text
alpha=0
-> 固定低 gain
-> rate-limited low gain
-> 候选完整配置
```

每一步都需要物理急停、joint limit 和人工接管。

### 第六步：选择模型并采集

选定 Task2 checkpoint 后：

- promote；
- 用同一 checkpoint 进行 filtered capture；
- 每个 episode 记录 provenance；
- 再做质量门；
- 再进入 ACT 数据转换。

---

## 7. 当前工作区状态

尚未提交的模型：

```text
artifacts/filter_reference_20260910/
```

尚未提交的代码：

```text
src/teleop_filter/
tools/learned_filter_worker.py
tools/learned_filter_ros_adapter.py
tools/train_trajectory_filter.py
tools/evaluate_trajectory_filter.py
tools/promote_runtime_model.py
tools/run_filter_ablations.py
config/filters/
config/runtime/learned_filter*.yaml
tools/tests/test_reference_filter_compatibility.py
```

文档：

```text
docs/0911_filter文档.md
docs/dilter模型选择和部署采集.md
```

注意：

- 当前没有创建 git commit；
- 模型目录仍是 untracked；
- 当前还在 `fsh/humble`；
- 设备未连接，不能把兼容测试通过理解为真机选型完成；
- 当前最重要的决策是 Task2 采用 fixed-gain 选型，还是先重训 gain-enabled filter。

---

## 8. Task2 六模型离线筛选结果（2026-09-11）

### 8.1 离线筛选范围

本轮只筛选 Task2 / button 的 6 个归档模型：

```text
cvae_seed7.pt
cvae_seed17.pt
cvae_seed27.pt
deterministic_seed7.pt
deterministic_seed17.pt
deterministic_seed27.pt
```

数据来源：

```text
artifacts/filter_reference_20260910/evidence_freeze.json
```

每个模型使用相同任务数据：

```text
episodes: 14
windows: 9196
target: joint_reference_action_rad
target semantics: delta_from_last_executed
```

所有模型参数量相同：

```text
899,544 parameters
```

### 8.2 筛选方法

当前归档只有聚合指标，没有逐窗口 prediction，因此本轮采用三级筛选：

1. **预测误差主排序**
   - MAE；
   - RMSE；
   - first-step MAE。

2. **seed 稳定性**
   - 比较 CVAE seed 7/17/27 的波动；
   - 比较 deterministic seed 7/17/27 的波动；
   - seed 波动大时，不优先选择偶然最优 seed。

3. **算法对照**
   - 从 CVAE 中选主候选；
   - 从 deterministic 中选最优对照；
   - 真机至少保留一个 deterministic 对照，避免把 CVAE 的种子偶然性误判为算法优势。

综合分数采用：

```text
score = 0.50 * MAE / best_MAE
      + 0.20 * RMSE / best_RMSE
      + 0.30 * first_step_MAE / best_first_step_MAE
```

分数越低越好。该权重强调：

- 整体 MAE；
- 首步预测精度；
- RMSE 次之。

### 8.3 六模型完整指标

| 模型 | MAE | RMSE | First-step MAE | 综合分数 |
|---|---:|---:|---:|---:|
| CVAE seed7 | 0.006582935 | 0.014683522 | 0.004147861 | **1.000690** |
| CVAE seed17 | 0.006598788 | 0.014708095 | 0.004162430 | **1.003284** |
| CVAE seed27 | 0.006689956 | 0.014783626 | 0.004235218 | 1.016506 |
| deterministic seed17 | 0.008043052 | 0.014633007 | 0.005101202 | 1.179853 |
| deterministic seed7 | 0.008152861 | 0.015258349 | 0.005072421 | 1.194659 |
| deterministic seed27 | 0.009014158 | 0.015613470 | 0.005734859 | 1.312844 |

分项排名：

| 模型 | MAE rank | RMSE rank | First-step rank |
|---|---:|---:|---:|
| CVAE seed7 | 1 | 2 | 1 |
| CVAE seed17 | 2 | 3 | 2 |
| CVAE seed27 | 3 | 4 | 3 |
| deterministic seed17 | 4 | 1 | 5 |
| deterministic seed7 | 5 | 5 | 4 |
| deterministic seed27 | 6 | 6 | 6 |

关键观察：

- CVAE 的三个 seed 在 MAE 和 first-step 上都优于 deterministic；
- RMSE 结果混合：deterministic seed17 的 RMSE 最好，但它的 MAE 和 first-step 明显落后；
- first-step 对实时连续 filter 更重要，因此 CVAE 更适合作为主候选；
- deterministic seed17 仍是必要的算法对照。

### 8.4 Seed 稳定性

CVAE button MAE：

```text
min = 0.006582935
max = 0.006689956
range = 0.000107021
```

deterministic button MAE：

```text
min = 0.008043052
max = 0.009014158
range = 0.000971106
```

结论：

- CVAE 的跨 seed MAE range 约为 deterministic 的 1/9；
- CVAE 的结果更稳定；
- deterministic 对 seed 明显更敏感，单独挑一个 seed 容易高估算法能力。

### 8.5 Baseline 对比

Task2 baseline：

```text
persistence MAE:        0.006514349
constant-velocity MAE:  0.003865528
```

对比：

- CVAE seed7 比 persistence 约差 1.05%：
  ```text
  (0.006582935 - 0.006514349) / 0.006514349 = +1.05%
  ```
- 所有学习模型也仍差于 constant-velocity baseline：
  - CVAE seed7 约差 70.3%；
  - deterministic seed17 约差 108.1%。

解释：

- 当前模型已经学到一定的短时动作预测能力；
- 但现有证据不足以证明它优于简单运动先验；
- 真机“丝滑程度”可能来自过滤、低增益或延迟，而不一定来自模型有效性；
- 因此不能只凭手感和单一 MAE 结论选择最终模型。

### 8.6 CPU 推理 sanity check

在 CPU 上对六个模型进行等价输入 microbenchmark：

| 模型 | P50 | P95 | 参数量 |
|---|---:|---:|---:|
| CVAE seed17 | 1.236 ms | 1.626 ms | 899,544 |
| CVAE seed27 | 1.848 ms | 2.057 ms | 899,544 |
| CVAE seed7 | 1.819 ms | 1.849 ms | 899,544 |
| deterministic seed17 | 1.825 ms | 1.893 ms | 899,544 |
| deterministic seed27 | 1.805 ms | 1.920 ms | 899,544 |
| deterministic seed7 | 1.799 ms | 1.831 ms | 899,544 |

注意：

- 六个模型参数量和网络结构相同；
- 上述是随机输入 CPU microbenchmark；
- 差异主要来自测量噪声；
- 不能代替真实 GPU + SigLIP2 + socket 的端到端 latency。

### 8.7 离线筛选结论

真机候选建议按以下顺序进入测试：

| 顺序 | 候选 | 用途 |
|---|---|---|
| 1 | `button/cvae_seed7.pt` | Task2 主候选，综合第一 |
| 2 | `button/cvae_seed17.pt` | CVAE seed 稳定性对照 |
| 3 | `button/deterministic_seed17.pt` | deterministic 算法对照 |
| 4 | `button/deterministic_seed7.pt` | 备用对照，暂不入首轮真机 |
| 5 | `button/cvae_seed27.pt` | 备用，MAE/RMSE/first-step 均略差 |
| 6 | `button/deterministic_seed27.pt` | 当前不建议进入真机 |

最终建议：

```text
主候选：button/cvae_seed7.pt
算法对照：button/deterministic_seed17.pt
seed 对照：button/cvae_seed17.pt
```

### 8.8 真机测试前置条件

当前归档模型 `alpha=0`，直接部署真机不会改变动作。因此真机测试前必须先确定：

#### 方案 A：fixed-gain 测试

- 使用同一个 action predictor；
- 在 runtime 外增加显式固定 authority；
- 建议从低 gain 开始，例如 `alpha=0.10`；
- 只用于 action backbone 选型，不用于证明 rate-limited gain。

#### 方案 B：先补训 gain-enabled filter

- 保留 action head；
- 训练 gain head；
- 使用 `authority_mode=rate_limited`；
- 之后才可验证分支真正的 continuous filter 算法。

在没有完成 A 或 B 前：

- 候选可以做 shadow；
- 不能声称已经完成 active filter 真机验证；
- 不能让 `alpha=0` 的模型进入正式 filtered data collection。

### 8.9 真机测试方案

同一 Task2、同一操作员、同一物体摆放条件和同一相机布置下进行。

试验顺序：

```text
raw teleoperation baseline
-> cvae_seed7
-> cvae_seed17
-> deterministic_seed17
```

每个候选至少完成：

```text
5 次有效重复
```

采用随机顺序，避免疲劳和熟悉度偏向某一个模型。

每轮记录：

- terminal success/failure；
- 完成时间；
- correction 次数；
- 人工接管次数；
- joint velocity；
- joint acceleration；
- jerk；
- 命令反转和突变；
- alpha、residual、clipping、fallback；
- model latency P50/P95/P99；
- 操作员主观评分：
  - 丝滑度；
  - 可控性；
  - 信心；
  - 疲劳；
  - 是否感觉模型在“抢控制权”。

真机选型时不能只看丝滑度。最终评分建议：

```text
任务成功率       30%
完成时间         15%
修正/接管次数    20%
jerk/速度突变    15%
latency          10%
主观可控性       10%
```

如果两个候选差距很小，优先选择：

1. seed 更稳定的 CVAE；
2. 延迟更低的模型；
3. 更少接管和修正的模型；
4. 主观感觉更可控的模型。

### 8.10 当前最终候选

进入真机测试的首轮候选：

```text
主候选：
artifacts/filter_reference_20260910/checkpoints/button/cvae_seed7.pt

seed 对照：
artifacts/filter_reference_20260910/checkpoints/button/cvae_seed17.pt

deterministic 对照：
artifacts/filter_reference_20260910/checkpoints/button/deterministic_seed17.pt
```

当前不能直接 active 的原因仍然是：

```text
归档 checkpoint 无 gain_head
authority_mode=zero
```

真机测试前需要先补 fixed-gain 测试入口，或者补训 gain-enabled Task2 filter。

---

## 9. 分支数采链路与模型完整性核查（2026-09-11）

### 9.1 模型有没有拉全

回答：**模型没有漏拉，12 个都是完整 checkpoint。**

`841f132` 中与 filter 产物有关的文件共 15 个：

```text
README.md
CHECKSUMS.sha256
evidence_freeze.json
12 × *.pt
```

按分支树核对：

| Task | 模型 | 数量 |
|---|---|---:|
| button | CVAE seed7/17/27 + deterministic seed7/17/27 | 6 |
| screwdriver | CVAE seed7/17/27 + deterministic seed7/17/27 | 6 |
| 合计 | | 12 |

完整性证据：

- 12 个 `.pt` 都是实际 PyTorch 文件，不是 Git LFS pointer；
- 每个文件约 3.6 MB；
- 每个 checkpoint 参数量为 899,544；
- `TrajectoryFilterRuntime.load()` 可加载；
- 12/12 SHA-256 校验成功；
- 每个 checkpoint 都包含 `model_state`、`model_config`、normalization、visual encoder provenance；
- `evidence_freeze.json` 中正好记录 12 个 run。

因此“模型很小”本身不是问题。当前模型确实只有约 0.9M 参数，视觉成本主要在冻结的
SigLIP2 encoder，不在 filter checkpoint。

但是分支只归档了 action-reference checkpoint，没有归档：

- 带 gain head 的 rate-limited checkpoint；
- fixed-gain 训练产物；
- risk-conditioned authority 训练产物；
- promoted runtime YAML。

这些不是“拉取不完整”，而是分支中没有对应训练产物。

### 9.2 分支有没有数采链路

回答：**有完整数采链路，但不是本机当前版本的直接替代。**

分支包含：

- `scripts/start_capture_session.sh`
- `scripts/start_model_deployment.sh`
- `scripts/start_learned_filter.sh`
- `tools/capture_manager.py`
- `tools/capture_episode.py`
- `tools/learned_filter_worker.py`
- `tools/learned_filter_ros_adapter.py`
- `tools/model_deployment_supervisor.py`
- `config/runtime/learned_filter*.yaml`
- `config/runtime/model_deployment.yaml`
- `config/capture_session_task2_filter.env`

分支链路设计：

```text
RealSense 双相机
+ LinkerTA 主臂
+ robot joint state
        |
        v
learned_filter_worker
        |
        v
learned_filter_ros_adapter
        |
        v
model_deployment_supervisor
        |
        v
teleop_control_bridge
        |
        v
lbot_driver / 真机
```

`capture_manager.py` 能把 filter worker、adapter 和 deployment supervisor 纳入 GUI
采集会话，并把 filter 候选、filter output 和 diagnostics topics 加入 rosbag。

### 9.3 分支原样是否能直接适配本机

回答：**不能直接按分支原样使用，需要当前本机版本做适配。**

#### 缺口 1：Task2 数据路径是旧盘路径

分支：

```text
/media/fanshihao/UBUNTU 20_0/task_button_press
```

当前该路径不存在。本机当前配置已经改为：

```text
/media/fanshihao/Cyan_data/ICRA2027_DATA/Task_Data/Task2_Data
```

#### 缺口 2：promoted filter 配置路径失效

分支的 Task2 filter env 指向：

```text
/media/fanshihao/UBUNTU 20_0/task_button_press/filter_runs/round1/filter-promoted-round1.yaml
```

该路径同样不存在。

#### 缺口 3：分支默认是 shadow，本机当前已改成 active-only 边界

分支：

- `model_deployment.yaml` 中有 `mode: shadow`；
- `start_model_deployment.sh` 支持 `--shadow`；
- `start_capture_session.sh` 默认给 filter deployment 传 `--shadow`。

本机当前：

- 已移除 shadow 分支；
- 使用显式 `--confirm=I_UNDERSTAND_MODEL_DEPLOYMENT`；
- deployment supervisor 是最终 active 录取边界。

因此不能直接把分支的 capture 脚本覆盖到本机，否则会把本机当前的 active-only
安全流程回退成 shadow 流程。

#### 缺口 4：分支没有本机后续数据盘和环境适配

本机当前 `fsh/humble` 相对分支 merge-base 还包含：

- 数据盘自动查找；
- `${TELEOP_DATA_ROOT}` 路径展开；
- ACT/filter 部署启动竞态修复；
- adapter diag 日志节流；
- Task1/Task2/Task3 本机 runtime 模板。

这些改动不能丢弃。本次只把实验分支的 filter 核心、worker/runtime 语义和配置接入
当前工作区，没有回退本机数采部署改动。

#### 缺口 5：assisted-round provenance 尚未完整接入

分支的 `b13d58d` 增加了：

- `collection_round`
- `control_mode`
- `filter_checkpoint`
- raw / filter / executed action 关系校验

这些对“后续含 filter 数据送入 ACT”很重要。当前只完成了 model/runtime/worker 核心
兼容，尚未把完整 provenance 改动合入当前数采和 flywheel 链路。

#### 缺口 6：分支 worker 原样不能加载这 12 个 checkpoint

分支原样存在：

- 不识别 `zero_initialize_action_head`；
- 不识别 `delta_from_last_executed`；
- worker 对 delta prediction 错误减去 baseline。

当前工作区已经修复这些问题，所以不能直接 checkout 分支，而应该继续在已适配的
当前工作区上维护。

### 9.4 当前最合理的数采适配方式

不要直接用分支覆盖本机链路，也不要重新从分支 checkout 开始。

应在当前 `fsh/humble` 工作区保留：

- 本机的数据盘和路径适配；
- 本机的 active deployment 边界；
- 本机日志和环境逻辑；
- 当前已完成的 12 checkpoint 加载兼容。

然后只吸收分支中尚缺的：

- assisted-round provenance；
- 与 filter collection 相关的 canonical/export 字段；
- 必要的数据采集验证测试。

最终链路应是：

```text
当前本机 capture/deployment 主干
+ 841f132 的新 filter runtime
+ 本机路径和环境适配
+ assisted-round provenance
```

### 9.5 总结

模型方面：

```text
12 个 checkpoint 已拉全
不存在缺失模型文件的问题
缺少的是 gain-enabled/fixed-gain 训练产物
```

数采方面：

```text
分支中有数采链路
链路结构适配 learned filter
但默认路径和 shadow/active 语义对本机已过时
需要与当前 fsh/humble 合并适配，不能直接覆盖
```

当前正确下一步：

```text
在当前工作区继续
-> 补 assisted-round provenance
-> 为 button 候选增加 fixed-gain 或 gain-enabled 测试入口
-> 接入 Task2 capture
-> shadow / low-gain 真机验证
-> 选择最终 filter
-> 再采集新的含 filter 数据
```

---

## 10. 控制/推理频率对 Filter 效果的影响

### 10.1 结论

会影响，而且影响可能很明显。

当前 filter 模型没有显式时间间隔输入：

```text
没有 dt
没有 timestamp embedding
没有 time-to-arrival
```

它只把连续采样点当作序列：

```text
history length = 16
horizon = 8
```

因此模型隐含假设：

```text
训练时相邻 row 的时间间隔
==
部署时相邻 inference 的时间间隔
```

如果训练和部署频率不一致，同一个模型会把相同数量的 step 解释成不同物理时间。

### 10.2 例如训练是 50 Hz，部署是 5 Hz

假设训练数据相邻控制点约为 20 ms：

```text
history 16 steps = 16 × 20 ms = 320 ms
horizon 8 steps  = 8 × 20 ms  = 160 ms
```

如果部署改成 5 Hz：

```text
每次 inference 间隔 = 200 ms
history 16 steps = 3.2 s
horizon 8 steps  = 1.6 s
```

时间尺度放大约 10 倍。

后果可能包括：

- 模型看到的是 3.2 秒历史，而训练时只见过 0.32 秒历史；
- 预测动作块理论覆盖 1.6 秒，而训练时只覆盖 0.16 秒；
- 控制更新延迟增加；
- 机械臂响应滞后；
- correction 开始时模型反应慢；
- 停止或修正后仍保持旧动作；
- 错过 correction 边界；
- 可能产生振荡、过冲或“黏滞感”；
- alpha/rate limit 和 SafetyProjector 虽然仍在保护，但无法修复时间语义错误。

这种问题不一定表现为离线 MAE 变差，因为离线评估仍可能按原训练序列计算。

### 10.3 当前链路中的频率

当前已知或常见配置：

```text
filter worker inference_hz: 5 Hz
RealSense capture FPS:      15 Hz
机器人状态常见频率:         约 50 Hz
主臂输入可能是:             约 50–100 Hz
```

并且之前的 ACT 链路已记录：

```text
相机 15 Hz / ACT 10 Hz / 机械臂 50 Hz
```

当前 filter 与 ACT 都存在频率链不一致问题。

但必须注意：**训练数据的真实控制步长目前没有写进归档 evidence。**
因此现在不能仅凭代码断言训练一定是 50 Hz 或 5 Hz。需要在原始训练数据、
`manifest.clock.control_hz`、实际 timestamp 间隔或 training report 中确认。

### 10.4 “快”和“慢”分别会怎样

#### 推理计算慢于定时器

如果一次推理耗时超过 inference period：

- adapter 会跳过后续提交；
- 下一次 timer 只检查 pending；
- 模型候选可能变旧；
- supervisor 可能 fallback；
- 最终表现为 filter 时有时无，而不是稳定辅助。

例如 5 Hz 的周期是 200 ms：

```text
模型 + SigLIP2 + JPEG + socket + ROS 必须在约 200 ms 内完成
```

否则模型效果会被延迟和 fallback 抹掉。

#### 部署频率低于训练频率

模型看到的时间被拉长：

- 历史窗口过长；
- horizon 过长；
- 反应滞后；
- 动作保持过久；
- 手感可能“钝”或“拖拽”。

#### 部署频率高于训练频率

模型看到的时间被压缩：

- history 覆盖时间过短；
- horizon 覆盖时间过短；
- 容易频繁改变预测；
- 可能显得抖动或抢控制；
- 不一定因为推理更快就更好。

#### 部署频率与训练频率一致

这是当前模型最基本的要求：

```text
相同采样步长
相同 history 时间跨度
相同 horizon 时间跨度
```

### 10.5 相机 15 Hz 与 filter 5 Hz 的关系

视觉 encoder 使用冻结 SigLIP2 embedding。

如果训练时：

```text
control/action row: 50 Hz
camera frame:       15 Hz
```

那么视觉 embedding 会被复用到相邻多个 control row 上。

运行时却是：

```text
filter inference: 5 Hz
camera frame:     15 Hz
```

虽然每 200 ms 都能拿到一帧新的视觉输入，但 action history 的时间步长仍然从训练时的
20 ms 变成了 200 ms。

因此“相机有 15 Hz”不能自动修复 action sequence 的时间尺度问题。

### 10.6 对 Task2 真机选型的要求

真机测试前必须增加频率一致性检查：

1. 从原始训练 validation episode 统计相邻 row 的 timestamp 间隔；
2. 得到训练步长：
   ```text
   median_dt_ms
   p05_dt_ms
   p95_dt_ms
   ```
3. 确认 filter runtime 的 inference period 是否匹配；
4. 分别按 50/25/10/5 Hz 对同一 episode 重采样并评估；
5. 观察 MAE、RMSE、first-step 和预测动作持续时间的退化；
6. 如果模型只在训练频率下有效，就保持训练频率，不直接改 `inference_hz`；
7. 如果算力不能达到训练频率，则应重新训练一个与部署频率一致、或带 `dt` 的模型。

### 10.7 推荐的部署频率策略

优先级从高到低：

#### 策略 A：训练频率部署

- 最安全；
- 保持完全一致的 step semantics；
- SigLIP2 可以按相机原频率更新，action state 按训练频率推理；
- 需要满足算力和 latency 要求。

#### 策略 B：降频训练 + 降频部署

- 先按目标频率重采样训练数据；
- 训练和部署都使用同一频率；
- 例如统一改为 10 Hz 或 5 Hz；
- 不能只改变 runtime，不改变训练。

#### 策略 C：时间间隔感知模型

- 输入加入 `dt`、timestamp 或 time embedding；
- 训练时覆盖不同频率；
- 运行时允许可变采样间隔；
- 当前归档模型不具备这个能力。

### 10.8 真机指标

频率问题需要单独记录：

- inference P50/P95/P99；
- input age；
- model age；
- pending skip 次数；
- candidate interval；
- fallback 次数；
- 命令保持时间；
- correction 触发到机械臂响应的延迟；
- jerk；
- 人工觉得“拖”“抖”“抢”“钝”的评分。

如果 filter 候选周期大于约 200 ms 或者输出长时间保持旧动作，当前 5 Hz 配置会直接
影响真机“丝滑程度”。

### 10.9 当前判断

当前不能仅凭 6 个 checkpoint 的离线 MAE 选择最终模型，因为：

```text
模型无时间输入
训练频率未记录在归档 evidence
当前 runtime 固定 5 Hz
相机/主臂/机器人频率不同
```

在确认训练步长之前：

- 可以完成模型结构、加载和离线误差初筛；
- 不能把真机手感差异完全归因于模型算法；
- 不能直接把 5 Hz 视为安全且等价于训练条件；
- 频率一致性应列入 Task2 真机测试的第一批验证项。

当前最重要的新增问题：

```text
这 12 个 checkpoint 的训练数据相邻控制 step 是多少 Hz？
```

如果该问题不能从数据 manifest 或 training report 得到答案，就需要在原始训练 episode 上
重新统计 timestamp 间隔，然后再进行真机选型。

---

## 11. 基于本机知识库的本地选择、部署与采集方案

### 11.1 知识库复核结论

知识库路径：

```text
/home/fanshihao/Desktop/knowledge/ICRA2027
```

重点文档：

- `3个task的filter完整流程.md`
- `问题与解决.md`
- `学习.md`
- `算法改进.md`
- `仓库导览.md`
- `针对挂载盘数据管理.md`
- `数采+act+推理问题.md`

可复用的已验证事实：

1. Task2 已跑通过：
   ```text
   prepare -> train -> evaluation -> promote -> deployment graph -> rosbag audit
   ```
2. Task2 数据路径：
   ```text
   /media/fanshihao/Cyan_data/ICRA2027_DATA/Task_Data/Task2_Data
   ```
3. 双相机硬要求：
   ```text
   main_rgb
   auxiliary_rgb
   ```
   第二路无帧时 adapter 会拒绝推理，这是正确保护，不是模型故障。
4. 4 键 correction 标注是硬编码的：
   ```text
   4 = correction_toggle
   ```
   但已有数据中人工标注不完整，必须在训练前统计 correction 覆盖率。
5. filter 和 ACT 共用：
   ```text
   model_deployment_supervisor
   -> teleop_control_bridge
   -> lbot_driver
   ```
6. active 真机需要显式人工确认和物理 E-stop。
7. 数据盘会漂移：
   ```text
   Seagate Hub -> Cyan_data -> robot_data
   ```
   ACT 已使用 `${TELEOP_DATA_ROOT}`，但 filter/flywheel/capture 路径还没有完全统一。
8. 已知频率链：
   ```text
   camera: 15 Hz
   robot/joint control: 50 Hz
   ACT candidate: 10 Hz
   filter candidate: 5 Hz
   ```
9. 知识库已经明确记录 ACT 真机效果差可能与频率不一致有关。
10. 知识库中 filter 16 帧被描述为约 0.32 s，同时 runtime 又按 0.2 s 一次推理，这两个描述暗示了潜在的训练/部署时间尺度不一致。

### 11.2 当前方案必须先解决的三个硬问题

#### 硬问题 1：归档模型没有 gain head

当前 Task2 六个 checkpoint：

```text
authority_mode=zero
gain_enabled=false
无 gain_head
```

直接部署没有辅助效果。

因此本机方案必须选择：

```text
短期：fixed-gain action filter，用于先选 action backbone
长期：重训 gain-enabled filter，用于论文主方法
```

#### 硬问题 2：训练频率未知或与部署 5 Hz 不一致

模型没有 `dt` 输入，16 个 history slot 和 8 个 horizon slot 是固定 step 数。

所以部署前必须从原始训练 view 统计：

```text
median_dt_ms
p05_dt_ms
p95_dt_ms
```

判断：

```text
训练 step == runtime step
```

如果训练 view 是 20 ms/step，则 runtime 不能直接使用 200 ms/step；否则历史窗口会从
约 0.32 s 变成 3.2 s，horizon 会从约 0.16 s 变成 1.6 s。

#### 硬问题 3：episode 边界没有复位

worker 已提供 `reset_episode`，但 adapter/capture 链路没有在新 episode 开始时发送复位请求。

后果：

- 上一个 episode 的 16 帧历史会泄漏到下一个 episode；
- alpha 可能跨 episode 保留；
- 第一个预测可能受上一次任务结束姿态影响；
- 数据 provenance 虽然正确，但模型输入连续性是错的。

正式 filtered capture 前必须：

```text
episode start
-> adapter 发送 reset_episode
-> worker 清空 commands/states/visuals/alpha/safety history
-> warmup
-> 才允许发布 filter candidate
```

### 11.3 推荐本地方案：两阶段路线

#### 阶段 A：fixed-gain 选 action backbone

目的：先回答“六个 action checkpoint 哪个在真机上更合适”。

特点：

- 不伪装成 gain-enabled continuous filter；
- 固定 `alpha`；
- 使用 `predicted_residuals * alpha`；
- 可以保持安全限幅、rate limit 和 fallback；
- 只用于模型筛选。

候选：

```text
cvae_seed7
cvae_seed17
deterministic_seed17
```

建议初始：

```text
fixed alpha = 0.10
```

如果行为太弱，可按安全审批升级到：

```text
fixed alpha = 0.20 或 0.25
```

但不能每个模型使用不同 alpha，否则无法公平比较。

#### 阶段 B：重训 gain-enabled filter

选出 action backbone 后：

- 使用相同 Task2 数据；
- 训练 gain head；
- 使用 `authority_mode=rate_limited`；
- 固定同一数据 split；
- 比较 fixed / framewise / rate-limited；
- 重新真机测试 gain 曲线和接管行为。

最终只把通过阶段 B 的模型用于正式含 filter 数据采集。

### 11.4 本机部署前准备

#### 路径准备

先探测数据盘：

```bash
cd /home/fanshihao/Desktop/dev/ICRA2027_TELEOP
bash scripts/resolve_data_disk.sh
```

Task2 数据根：

```text
<DATA_ROOT>/Task_Data/Task2_Data
```

模型 cache：

```text
/media/fanshihao/Seagate Hub/ICRA2027_DATA_TASK2/vlm_cache
```

如果盘发生漂移，优先把 SigLIP2 cache 纳入统一模型根，或为 filter 增加
`TELEOP_MODEL_ROOT`。

#### 代码准备

必须保留：

- 当前本机 active-only deployment；
- 本地 `paths_env` 路径展开；
- adapter 日志节流；
- 12 checkpoint 兼容；
- worker `reset_episode`；
- assisted-round provenance。

#### 模型准备

建议把候选放入稳定目录：

```text
models/filter_reference_20260910/button/
```

或继续使用：

```text
artifacts/filter_reference_20260910/checkpoints/button/
```

但 promoted YAML 必须写绝对路径和 SHA-256。

### 11.5 离线与无硬件验证

#### Step 1：再次验证 checkpoint

```bash
sha256sum -c artifacts/filter_reference_20260910/CHECKSUMS.sha256
```

#### Step 2：验证候选 inference

至少确认：

- checkpoint 可加载；
- 输入 shape 正确；
- 两路视觉 embedding 正确；
- `predicted_residuals` 正确；
- fixed authority 生效；
- `alpha=0` 时 residual=0。

#### Step 3：统计训练 step

从已有 validation view 或原始 canonical control stream 统计：

```text
timestamp_ns diff
```

输出：

- median；
- p05；
- p95；
- 频率 histogram。

#### Step 4：确定 runtime rate

```text
如果训练是 50 Hz -> runtime 应尽量 50 Hz，或重新按 5/10 Hz 训练
如果训练是 5 Hz  -> runtime 5 Hz 可以保留
如果训练模型无法确认 -> 先不要真机 active
```

### 11.6 真机 Shadow/Low-gain 选型

#### 先做 shadow

- raw command 始终直接控制；
- filter 只输出 diagnostics；
- 验证相机、状态、时间戳和 latency。

#### 再做低 gain active

同一 Task2、同一操作员、同一初始姿态：

```text
raw baseline
cvae_seed7 @ alpha=0.10
cvae_seed17 @ alpha=0.10
deterministic_seed17 @ alpha=0.10
```

每个候选至少 5 次有效重复。

记录：

```text
success
time
correction_count
takeover_count
jerk
joint velocity
command reversal
alpha
residual
clipping
fallback
latency P50/P95/P99
操作员丝滑度/可控性评分
```

推荐评分：

```text
成功率         30%
完成时间       15%
修正/接管次数  20%
jerk/突变      15%
latency        10%
主观可控性     10%
```

### 11.7 本机采集方案（选定 filter 后）

先做软件冒烟：

```bash
cd /home/fanshihao/Desktop/dev/ICRA2027_TELEOP
conda activate teleop

bash scripts/start_learned_filter.sh <promoted-filter-yaml>
```

看到：

```text
[READY] learned-filter worker
```

后停止。

真机 Task2 含 filter 采集：

```bash
bash scripts/start_capture_gui.sh \
  --config=config/capture_session_task2.env \
  --learned-filter-config=<promoted-filter-yaml> \
  --model-confirm=I_UNDERSTAND_MODEL_DEPLOYMENT \
  --real \
  --physical-estop-ready \
  --confirm=I_UNDERSTAND_REAL_ROBOT
```

真机前检查：

- 数据盘 `rw`；
- CAN 正常；
- 主臂能遥操；
- 两路相机均稳定出帧；
- 机械臂状态 topic 在线；
- physical E-stop 可达；
- operator/auditor ID 正确；
- correction 标注员知道使用 `4` 键。

采集过程中检查：

```bash
source /opt/ros/humble/setup.bash
ros2 topic hz /teleop_filter/right_arm_joint_control
ros2 topic hz /model_deployment/right_arm_joint_control
ros2 topic hz /camera2/camera/color/image_raw
```

新数据落盘：

```text
<DATA_ROOT>/Task_Data/Task2_Data/<new_episode>/
```

rosbag 至少包含：

- raw teleoperation；
- filter candidate；
- filter diagnostics；
- deployment output；
- mapped command；
- robot state；
- 双相机图像；
- audit events。

### 11.8 采集后的回流流程

新数据只做增量 prepare：

```bash
conda activate teleop
bash scripts/task2_prepare_filter_data.sh
```

新一轮训练：

```bash
TASK2_ROUND=round2 bash scripts/task2_train_filter.sh
bash scripts/task2_evaluate_filter.sh
```

然后 promote 新 round：

```bash
bash scripts/promote_model_checkpoint.sh --kind filter \
  --checkpoint <round2>/model/trajectory_filter.pt \
  --template config/runtime/learned_filter_task2_local.yaml \
  --output <round2>/filter-promoted-round2.yaml
```

### 11.9 送入 ACT

CAN/Action contract：

```text
arm7
```

转换入口：

```bash
bash scripts/convert_episode_to_lerobot.sh --run-dir <episode-dir>
```

必须记录：

- action 是 raw、filter output 还是 executed action；
- filter checkpoint SHA-256；
- collection round；
- control mode；
- correction mask；
- task/objective。

建议保留两套数据集：

```text
raw-only
filtered
```

分别训练 ACT 并比较：

```text
成功率
完成时间
轨迹误差
jerk
接管次数
策略稳定性
```

不能把 raw 和 filtered 数据在未区分 action 语义的情况下直接混合送入 ACT。

### 11.10 本方案最终验收条件

Task2 filter 选型通过的最低条件：

1. checkpoint 和 SHA-256 均可验证；
2. 双相机和状态输入稳定；
3. 训练/运行 step 一致或有明确重采样；
4. episode 边界复位；
5. 模型候选无 timeout/fallback 异常；
6. shadow 行为稳定；
7. 低 gain active 可控；
8. 相比 raw baseline 不损害成功率；
9. 修正次数或完成时间至少一项改善；
10. latency 和 fallback 在可接受范围内；
11. 新数据 provenance 完整；
12. 通过数据质量门后才进入 ACT。

最终策略：

```text
Task2
-> 固定候选 cvae_seed7 / cvae_seed17 / deterministic_seed17
-> 频率合规检查
-> fixed-gain shadow/low-gain 选型
-> 选择一个 action backbone
-> 重训 gain-enabled filter
-> 真机复核
-> 正式含 filter 数据采集
-> 回流 Task2 round2
-> 数据集分流后训练 ACT
```

---

## 12. 硬件接入后的实际核查（2026-09-11）

### 12.1 环境

Teleop Conda：

```text
/home/fanshihao/miniforge3/envs/teleop
```

实测：

```text
torch 2.6.0+cu124
CUDA available: True
GPU: NVIDIA GeForce RTX 4060 Laptop GPU
```

### 12.2 SigLIP2 权重

已找到：

```text
/media/fanshihao/Seagate Hub/ICRA2027_DATA_TASK2/vlm_cache/
  models--google--siglip2-base-patch16-224/
  snapshots/75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2/model.safetensors
```

文件：

```text
model.safetensors: 1,500,800,904 bytes
```

revision 与 checkpoint 要求完全一致。

### 12.3 部署环境冒烟

使用：

```text
config/runtime/filter-task2-cvae-seed7-selection.yaml
```

结果：

```text
[READY] learned-filter worker
```

说明：

- filter checkpoint 可加载；
- SigLIP2 可加载；
- GPU 可用；
- worker 已进入 ready；
- adapter 能启动并等待真实输入。

当前 ROS 只看到：

```text
/parameter_events
/rosout
```

相机、主臂、机械臂驱动尚未启动，因此 adapter 当前报告：

```text
missing=['master', 'state', 'main_rgb', 'auxiliary_rgb']
```

这是硬件图未启动，不是模型故障。

### 12.4 Task2 数据

当前 Task2 数据：

```text
/media/fanshihao/robot_data/ICRA2027_Data/Task2_Data
```

共：

```text
102 条 episode
```

当前文件系统状态：

```text
read-only
```

可以读取和做频率审计，但在恢复为 read-write 前不能安全开始新采集。

### 12.5 真实训练 step 频率

从 Task2 第一条 episode 的实际 rosbag 导出并统计：

```text
median_dt_ms: 20.002444
median_hz:    49.99389074655077
p05_dt_ms:    19.9001482
p95_dt_ms:    20.122163
history 16:   0.320039104 s
horizon 8:    0.160019552 s
```

结论：

```text
filter 训练 step 是确定的约 50 Hz
```

之前 runtime 的 5 Hz：

```text
runtime dt:         200 ms
runtime history:    3.2 s
runtime horizon:    1.6 s
time scale ratio:   约 10 倍
```

因此 5 Hz 配置不能直接用于当前归档模型。三个 Task2 selection runtime 已改为：

```text
inference_hz: 50.0
```

### 12.6 GPU 延迟

实测窗口：

- filter action model：P50 约 1.1 ms，P95 约 1.7 ms；
- SigLIP2 双相机图像编码：P50 约 20.6 ms，P95 约 21.2 ms。

同步执行两者时：

```text
P50 约 21.6 ms
P95 约 22.4 ms
```

因此：

- 动作模型本身能满足 50 Hz；
- SigLIP2 encoder 是瓶颈；
- 不能在每个 20 ms step 都重新编码两路图像。

处理方式：

```text
action model: 50 Hz
camera embedding: 15 Hz
复用最近一帧 embedding 最多 2-3 个 action steps
```

worker 已加入按 camera timestamp 缓存视觉 embedding：
- camera stamp 未变化时直接复用；
- camera stamp 变化时重新编码。

100 个 50 Hz 模拟 step、15 Hz 图像更新的测试结果：

```text
P50: 1.517 ms
P95: 22.34 ms
mean: 10.482 ms
ready steps: 84/100
```

84 个 ready step 正好对应排除前 16 步 warmup 后，其余都处于可推理状态。实际机器上仍需测 ROS/JPEG/socket 总延迟。

### 12.7 alpha=0 的结论

盘上和仓库中没有找到带 gain head 的其他 Task2 filter checkpoint。

当前 12 个 checkpoint：

```text
gain_enabled=false
无 gain_head
authority_mode=zero
```

因此 alpha=0 无法通过加载方式解决，只能重新训练 gain-enabled 模型。

当前选择：

```text
短期选型直接使用 fixed authority
fixed_authority=0.10
```

三个候选 runtime 已生成并固定 SHA-256：

```text
config/runtime/filter-task2-cvae-seed7-selection.yaml
config/runtime/filter-task2-cvae-seed17-selection.yaml
config/runtime/filter-task2-deterministic-seed17-selection.yaml
```

### 12.8 本机空间

本机系统盘：

```text
67 GB total, 60 GB used, 3.9 GB free
```

已明确：

```text
任何 episode、rosbag 解包、derived、训练输出、TensorBoard、模型结果
均不得写入本机项目盘或 home 盘。
```

频率审计临时数据已从 `/tmp` 删除。

### 12.9 当前部署状态

```text
[READY] CUDA
[READY] teleop conda
[READY] SigLIP2 weights
[READY] checkpoint compatibility
[READY] filter worker
[READY] fixed-gain selection runtime
[READY] episode reset
[BLOCKED] hardware ROS graph not running
[BLOCKED] robot_data filesystem is read-only
[PENDING] real worker latency with live camera/JPEG/socket
```

当前不能直接开始写数据，原因是数据盘仍是只读挂载。
