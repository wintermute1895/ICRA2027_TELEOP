# Filter 链路与实验分支评估（2026-09-11）

> 被评估引用：`origin/exp/continuous-filter-backbone-spike = 841f132`
> 当前工作区：`fsh/humble = 95f7c88`
> 两者 merge-base：`f0f075f`
> 当前工作区相对 merge-base 领先 3 个提交；实验分支相对 merge-base 领先 8 个提交。
>
> 本文件结论以提交 `841f132` 的源码、配置和归档 checkpoint 元数据为准。归档
> checkpoint 已导出到 `artifacts/filter_reference_20260910/`，Task2 加载/推理兼容测试
> 已通过。本机 filter 链路已确认可以运行，但遥操设备当前未连接，因此真实设备推理、
> 时延和 active deployment 尚未验证。

---

## 0. 结论摘要

1. 实验分支的**目标算法**是：
   `因果历史编码器 + CVAE/确定性动作块头 + 独立连续 gain 头 + rate-limited alpha + residual bound + 独立 SafetyProjector`。
2. 相对当前 `fsh/humble` 的旧概率 gate 链路，这是实质升级方向，主要优势是辅助强度连续、可限速、动作方向与授权强度解耦、运行时安全检查更完整。
3. `841f132` 归档了 12 个模型，分别对应：
   - Task2：`button` 电源按钮；
   - Task3：`screwdriver` 螺丝刀对准。
   - 没有 Task1 `precision_alignment` 模型。
4. **归档模型已经可以加载和推理，但仍不能直接做 active continuous filter 部署**：
   - `zero_initialize_action_head`、`delta_from_last_executed` 和 worker residual 语义已完成兼容，并通过 Task2 回归测试；
   - 所有归档 checkpoint 实际都是 `authority_mode: zero`、`gain_enabled: false`，state dict 中没有 `gain_head`，因此 alpha 仍恒为 0，不会有任何辅助修正；
   - 归档模型可作为 action backbone、离线评估和 shadow 验证候选，但不能直接代表 continuous-gain filter；
   - 没有为这 12 个 checkpoint 生成 promoted runtime YAML，也没有同机同相机台架的真机有效性和时延证据。
5. 因此当前可行路径是：
   - 先做代码兼容、shadow/零增益链路验证；
   - 要真正采集“带连续辅助”的数据，必须重新训练 gain-enabled Task2/Task3 模型；
   - Task1 没有可用归档模型，需要单独训练。

---

## 1. `841f132` 与分支范围

`841f132` 本身只归档 formal joint-reference filter matrix，没有新增训练或部署代码：

- `artifacts/filter_reference_20260910/README.md`
- `artifacts/filter_reference_20260910/CHECKSUMS.sha256`
- `artifacts/filter_reference_20260910/evidence_freeze.json`
- 12 个 `*.pt` checkpoint，约 43.6 MB

归档证据明确说明：

- 原始 episode、图像、逐窗口预测、TensorBoard/W&B 和私有绝对路径均未上传；
- checkpoint 是离线实验产物；
- runtime deployment 状态为 `offline_and_simulation_only`；
- 正式真机使用前仍需通过 collection train-deploy contract。

分支从 merge-base 到 tip 的主要提交为：

| 提交 | 主要更新 |
|---|---|
| `4ff59aa` | 连续、限速辅助基线；动作块和 gain 控制 |
| `25e15b2` | learned filter 采集与部署链路整合 |
| `f65aa86` | 对齐论文契约：因果 mask、分离头、rate limit、SafetyProjector |
| `e8b40a8` | deterministic / CVAE / risk-conditioned authority 统一变体 |
| `b13d58d` | assisted-round action provenance 强制校验 |
| `841f132` | 归档 formal reference checkpoint 与证据 |

---

## 2. 分支目标算法

### 2.1 推理控制式

```text
delta_hat_t = clip(u_hat_demo_(t|t) - u_raw_t, -delta_max, delta_max)
alpha_bar_t = alpha_max * sigmoid(g_theta(h_t))
alpha_t = alpha_(t-1) + clip(alpha_bar_t - alpha_(t-1), -r_alpha, +r_alpha)
u_tilde_t = u_raw_t + alpha_t * delta_hat_t
u_out_t = SafetyProjector(u_tilde_t)
```

其中：

- `u_raw_t`：LinkerTA 原始遥操命令；
- `u_hat_demo_(t|t)`：模型的专家动作预测；
- `alpha_t`：连续辅助权限；
- `alpha_rate`：每步最大权限变化率；
- `SafetyProjector`：与学习模型独立的最终安全投影。

### 2.2 模型结构

分支主模型包含：

1. 16 帧因果历史 Transformer；
2. 动作维度 7，状态维度 7；
3. 命令历史维度 14：`7 维 raw command + 7 维 executed command`；
4. 两路冻结 SigLIP2-base 图像 embedding：`768 + 768 = 1536`；
5. 动作块 horizon：8；
6. CVAE 或 deterministic action head；
7. 独立 gain head；
8. 可选 risk-conditioned authority head。

分支支持的模型类型：

- `deterministic_action`：确定性动作预测消融；
- `cvae_rate_limited`：CVAE 动作预测，主配置意图是 rate-limited gain；
- `risk_conditioned_authority`：用 prediction discrepancy、CVAE dispersion 和 correction probability 风险特征生成 authority。

分支支持的 authority 模式：

`zero`、`fixed`、`binary_gate`、`framewise`、`rate_limited`。

### 2.3 训练与评估改动

- 动作重构损失在物理空间计算，避免只在归一化空间看起来正确；
- 新增 gain band loss：
  - correction 窗口鼓励较高 alpha；
  - nominal 窗口鼓励较低 alpha 和零 residual；
- 新增 correction/background 分项重构误差；
- 新增 gain mean、gain variation、AUPRC、interval IoU 等评估指标；
- 固定预算 ablation runner 提供 16 个变体；
- 严格 causal mask，避免历史窗口内未来 token 泄漏。

### 2.4 运行时安全改动

分支 worker 增加：

- 显式 `safety` 配置；
- joint position limit；
- residual magnitude limit；
- residual rate limit；
- command velocity limit；
- model age timeout；
- invalid value / stale input / worker error fallback；
- episode 级 `previous_alpha` 状态重置；
- `receding_horizon` 和 `open_loop_chunk` 两种执行模式。

分支 runtime YAML 的有效残差上限为 `0.01 rad`。虽然部分 checkpoint 元数据记录
`max_correction_rad: 0.05`，最终仍会被 runtime safety 配置进一步限制。

---

## 3. 与当前 `fsh/humble` 链路的比较

| 维度 | 当前 `fsh/humble` | 实验分支 `841f132` 目标架构 | 评价 |
|---|---|---|---|
| 辅助机制 | correction probability 乘 `residual_blend` | 独立 gain head + 连续 alpha 状态 | 分支改进 |
| 时间约束 | 无显式 authority rate limit | alpha 每步最多变化 `alpha_rate` | 分支改进 |
| 动作头 | 单一动作预测，gate 另头但不控制连续权限 | 动作头与 gain head 分离 | 分支改进 |
| horizon | 当前 YAML 为 1 | 目标配置为 8，receding horizon | 分支改进，但增加延迟风险 |
| 命令历史 | raw/controller 单通道语义 | raw + executed 双通道 14 维 | 契约更完整，需数据同版本 |
| 目标语义 | 显式 expert action，runtime 减 raw 得 residual | 期望统一 delta/executed-action 契约 | 分支方向正确，但归档模型未统一 |
| safety | worker 内简单 clip | 独立 SafetyProjector，含 velocity/age/fallback | 分支明显改进 |
| 数据 provenance | 较弱或依赖调用方 | round/control mode/checkpoint 强制记录 | 分支明显改进 |
| 训练评估 | 基础离线误差 | 物理空间误差、gain、消融、延迟缺口 | 分支更完整 |
| 可部署性 | 现有链路可运行 | 目标架构完整，但归档模型不兼容/不启用 gain | 目前不能直接 active |

### 3.1 当前本地算法实际是什么

当前工作区仍是旧链路：

```text
gate = sigmoid(gate_head(history))
residual = clip(predicted_residual * residual_blend * gate, -limit, +limit)
u_out = u_raw + residual
```

它虽然用概率值而非常见的硬 0/1 二值 gate，但本质仍是：

- action 与 correction probability 耦合在同一套旧 checkpoint 语义中；
- authority 没有独立训练目标；
- alpha 没有跨帧速率限制；
- 没有模型年龄、速度、measured-state 初值等完整投影；
- runtime 兼容旧 v0.1 checkpoint，但不能加载新 gain 模型。

### 3.2 分支真正带来的改进

分支最有价值的变化不是单纯“把 gate 换成 gain”，而是把以下三件事分开：

1. **动作方向预测**：`u_expert`；
2. **辅助权限预测**：`alpha`；
3. **安全执行**：`SafetyProjector`。

这使模型可以预测“应该修多少”，同时由另一个机制决定“现在允许施加多少”。对于精密
遥操采集，这比旧 gate 更容易做 nominal preservation、限速和消融解释。

---

## 4. 归档模型对应哪个 Task

### 4.1 Task 映射

| 归档目录 | Task | 模型数量 | 说明 |
|---|---|---:|---|
| `checkpoints/button` | Task2 电源按钮 `power_button_press_v1` | 6 | CVAE/deterministic × seed 7/17/27 |
| `checkpoints/screwdriver` | Task3 螺丝刀对准 `screwdriver_alignment_v1` | 6 | CVAE/deterministic × seed 7/17/27 |
| 无目录 | Task1 精密对准 `precision_alignment` | 0 | 需要重新训练 |

归档模型共有的技术元数据：

```text
action_dim: 7
state_dim: 7
command_dim: 14
history_length: 16
horizon: 8
visual_dim: 1536
latent_dim: 8
model_dim: 128
action_transform_id: right_arm_vendor_to_filter_v1
command_semantics: raw_and_executed_action_history
target_field: joint_reference_action_rad
target_semantics: delta_from_last_executed
camera_ids: [main_rgb, auxiliary_rgb]
visual_model: google/siglip2-base-patch16-224
visual_revision: 75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2
```

每个 checkpoint 的参数量约为 `899,544`。归档没有记录原始数据绝对路径，因此不能仅凭
`task=button/screwdriver` 证明它们来自本机当前台架、当前相机布置或当前数据版本。

### 4.2 离线汇总指标

按三个 seed 平均：

| Task | 模型 | MAE mean | RMSE mean | first-step MAE mean |
|---|---|---:|---:|---:|
| button | CVAE | 0.006624 | 0.014725 | 0.004182 |
| button | deterministic | 0.008403 | 0.015168 | 0.005303 |
| screwdriver | CVAE | 0.005415 | 0.012064 | 0.003497 |
| screwdriver | deterministic | 0.005798 | 0.012205 | 0.003748 |

baseline：

| Task | persistence MAE | constant-velocity MAE |
|---|---:|---:|
| button | 0.006514 | 0.003866 |
| screwdriver | 0.005442 | 0.003355 |

结论：

- CVAE 在汇总 MAE 上优于 deterministic；
- CVAE 略优于 persistence；
- 但当前汇总 MAE 仍差于 constant-velocity baseline；
- 因 baseline 未提供 same-granularity first-step 指标，不能据此宣称学习模型首步优于 baseline；
- 论文实验章节尚未补齐 bootstrap、latency 和 safety 证据。

每个 run 的 `missing_evidence` 都包括：

- `episode_paired_bootstrap`
- `nominal_correction_boundary`
- `one_euro_baseline`
- `no_vision_cvae`
- `runtime_latency`
- `safety_clipping`
- `run_evidence_retrospective_fields`

### 4.3 checkpoint 实际不是 continuous-gain 模型

这是当前最重要的问题。虽然模型目录名为 CVAE、`model_type` 写的是
`cvae_rate_limited`，但实际 checkpoint 配置是：

```text
authority_mode: zero
gain_enabled: false
gate_enabled: false
gain_head keys: 无
risk_head keys: 无
```

因此：

- 它们只训练了 action prediction；
- `_gain_outputs()` 在 `authority_mode=zero` 时直接返回 `alpha=0`；
- 即使模型能推理，输出 residual 也为 0；
- 不能把它们称为已经训练好的 continuous assistance filter；
- 它们更适合作为 action backbone / joint-reference baseline，而不是可直接采集辅助数据的产品模型。

另外，checkpoint 的 `selection.metric` 是 `validation.prior_mae_rad`，选中的 epoch 大多是
1 到 4，仅一个 deterministic 模型选择 epoch 37。下一步应核查训练曲线和 early-stop
策略，避免把偶然的最优 epoch 当成稳定模型。


### 4.4 这 12 个 checkpoint 能否直接用于算法比较

不能把它们理解为 12 种已经训练完成的 continuous-gain filter 算法。正确分类如下：

| 对比维度 | 是否可以比较 | 说明 |
|---|---|---|
| CVAE vs deterministic action backbone | 可以 | 每个 task 都有 2 种模型、各 3 个 seed |
| seed 稳定性 | 可以 | 比较同 task、同模型的 seed 7/17/27 |
| fixed gain / framewise gain / rate-limited gain | 不可以 | 归档 checkpoint 没有 gain head，且 authority 恒为 zero；需要重新训练或额外 fixed-gain runner |
| risk-conditioned authority | 不可以 | 归档中没有 risk-conditioned checkpoint |
| Task2 与 Task3 的模型效果 | 不建议直接比较 | 两个 task 的数据分布、参考动作和评价样本不同 |
| 真机“丝滑程度” | 当前不能作为 active filter 直接比较 | 归档模型可以加载，但不会输出非零 alpha |

因此它们适合回答“CVAE action head 是否优于 deterministic action head”这个问题，不能回答
“continuous filter 是否比 fixed gain 或 binary gate 更好”这个问题。后者必须重新训练带
gain head 的版本，并执行 `tools/run_filter_ablations.py` 中的消融。

### 4.5 真机验证与选模型应该怎么做

“丝滑程度”可以作为评价之一，但不能作为唯一选择标准。一个过于平滑、延迟过大或
过度压制操作的 filter，也可能产生看似丝滑但不可用的结果。建议针对每个 task 独立
选型，而不是为所有 task 选一个全局最佳模型。

推荐顺序：

1. **离线筛选**
   - 先验证 checkpoint 加载、target semantics 和 residual composition；
   - 比较 MAE、RMSE、first-step MAE；
   - 必须加入 persistence、constant-velocity、旧 gate 和 raw teleoperation；
   - 检查 seed 分散度，不直接选单个偶然最优 seed。

2. **推理与安全 bench test**
   - 不接机械臂控制路径；
   - 验证双相机顺序、SigLIP2 revision、GPU 吞吐和 socket E2E latency；
   - 记录 P50/P95/P99 latency、timeout、fallback、joint/residual/velocity clipping。

3. **真机 shadow test**
   - 操作员仍控制 raw command；
   - 模型只输出预测和候选 residual，不允许改变机械臂；
   - 对比候选模型在同一 task、同一操作员、同一初始条件下的输出稳定性。

4. **低权限 active test**
   - 从固定低 gain 开始，再做 rate-limited gain；
   - 每个候选模型使用相同 task、操作员、物体位置、试验次数和随机顺序；
   - 操作员可以随时接管，所有安全门必须有效。

5. **评价指标**
   - 任务成功率、完成时间、修正次数、接管次数；
   - 关节速度、加速度、jerk、命令反转和突变；
   - alpha、residual、clipping、fallback 和 latency；
   - 操作员主观评分：丝滑度、可控性、信心、疲劳；
   - 不能只比较视频观感或一次操作手感。

6. **按 task 选型**
   - Task2 比较 button 的 6 个模型；
   - Task3 比较 screwdriver 的 6 个模型；
   - Task2 与 Task3 分别产生最佳 checkpoint、最佳 alpha 上限和安全配置；
   - 最终选择应是“数据质量最好且不损害操作员控制权”的模型，而不只是最平滑的模型。

### 4.6 选中的 filter 数据如何送入 ACT

数据采集和 ACT 训练必须明确 action 语义：

- 如果 ACT 要学习“最终执行策略”，应使用 `executed_joint_command_rad`；
- 如果 ACT 要学习“人类原始意图”，应使用 raw/经过审计的目标动作；
- 不要把 raw、filter output、executed action 混为同一 action 字段；
- 每个 episode 必须记录 collection round、control mode、filter checkpoint 和 checkpoint SHA-256；
- 被 filter 改变过的 episode 必须可追溯到具体 filter 配置和 alpha；
- 建议至少保留一条 raw-only 对照链，并分别训练/评估 raw-ACT 与 filtered-ACT。

也就是说，流程应是：

```text
raw-only pilot
-> filter offline screen
-> shadow
-> low-gain real-robot validation
-> select best checkpoint per task
-> collect filtered episodes with full provenance
-> data quality gate
-> canonical / LeRobot projection
-> ACT training
-> raw vs filtered ACT A/B evaluation
```

在完成以上步骤前，不建议直接把某个归档模型作为正式数据采集策略。

---

## 5. 是否可以部署到本机

### 5.1 当前结论

**当前可以加载和运行这 12 个归档模型，但不能直接部署为 active filter。**

已解决项：

1. **checkpoint metadata 兼容**
   - `TrajectoryFilterConfig` 已接受 `zero_initialize_action_head`，该字段只作为训练来源元数据，不改变推理。
   - 12 个归档 checkpoint 均可在当前代码中构造和预测。

2. **target semantics 兼容**
   - runtime 已显式接受 `delta_from_last_executed`；
   - 该语义下 `predicted_residuals` 直接使用模型预测 delta。

3. **worker residual 组合兼容**
   - worker 改为使用 `prediction.predicted_residuals`，不再把 delta 与绝对 baseline 错误相减；
   - alpha 存在时使用 alpha，legacy gate 存在时使用 gate，两者都没有时保持 control-neutral。

剩余阻塞：

1. **没有 gain 参数**
   - 归档模型 state dict 没有 `gain_head`；
   - 即使把 `authority_mode` 改成 `rate_limited` 或 `gain_enabled=true`，也无法恢复未训练的 gain 权重；
   - active continuous assistance 必须重训，或在选型阶段明确只测试 fixed-gain action composition。

2. **没有 promoted runtime 配置**
   - `config/runtime/learned_filter.yaml` 仍是空 checkpoint 模板；
   - 需要 `promote_runtime_model.py` 生成带 SHA-256 的不可变配置。

3. **缺少同台架验证**
   - 归档证据没有本机 joint direction、相机外参、图像裁剪、相机顺序和实际 latency；
   - 即使离线 MAE 合理，也不能直接证明对当前 rig 有效。

4. **设备未连接**
   - 当前无法执行 topic-level E2E、真实 GPU 推理延迟、CAN/LinkerTA 收发和安全回退测试。

### 5.2 本机条件

已确认：

- 本机有 `NVIDIA GeForce RTX 4060 Laptop GPU`，8 GB 显存；
- 现有 SigLIP2 cache：
  `/media/fanshihao/Seagate Hub/ICRA2027_DATA_TASK2/vlm_cache`；
- 其中存在 checkpoint 要求的精确 revision
  `75de2d55ec2d0b4efc50b3e9ad70dba96a7b2fa2`；
- 模型本体只有约 0.9M 参数，关键显存成本主要来自 SigLIP2 和图像预处理；
- Task2 runtime 模板已指向存在的 SigLIP2 cache：
  `/media/fanshihao/Seagate Hub/ICRA2027_DATA_TASK2/vlm_cache`；
- 旧 Task2 数据路径 `/media/fanshihao/UBUNTU 20_0/task_button_press` 当前不存在；
- Task3 数据路径 `/media/fanshihao/Seagate Hub/ICRA2027/task3_Data` 存在。

这里的“本机条件”只说明静态环境和文件可用性；由于设备未连接，尚不能给出最终
可部署结论。

### 5.3 达到 active 部署所需条件

最低门槛：

1. （已完成）把实验分支的 filter/runtime/worker 合入当前 `fsh/humble`，保留本地
   `paths_env` 路径展开和 adapter 日志节流；
2. （已完成）兼容 checkpoint metadata、target semantics 和 worker residual composition；
3. （已完成）增加 12 个归档 checkpoint 加载/推理及 control-neutral 回归测试；
4. 为 Task2/Task3 各自重新训练 gain-enabled 模型；
5. 在 held-out episode 上评估动作误差和 gain 指标；
6. 记录 latency P50/P95/P99、裁剪率、fallback 次数和 model timeout；
7. 与 raw、persistence、constant-velocity、旧 gate、fixed gain 做同数据对比；
8. 通过 promote 工具固定 checkpoint 和 SHA-256；
9. 接设备后先做不写控制链路的 shadow 记录；
10. 再做零增益、低增益、rate-limited 分阶段 active 验证。

建议先用 Task2 button 验证整合链路，因为：

- 归档中已经有 button 模型；
- 本仓库之前已经跑通过 Task2 filter 工程链路；
- Task2 相机和 right-arm topic 契约已有本地配置基础。

Task3 可以作为第二个 task。Task1 没有归档模型，不能复用本次模型。


### 5.4 Task2 兼容性修复结果（2026-09-11）

已将实验分支的 filter 核心接入当前工作区，并完成以下兼容修改：

- `TrajectoryFilterConfig` 增加 inference-neutral 的
  `zero_initialize_action_head` 元数据字段；
- `TrajectoryFilterRuntime` 接受 `delta_from_last_executed`；
- worker 不再执行错误的 `(predicted_action - baseline)`，统一使用
  `predicted_residuals`；
- worker authority 优先级改为 `alpha -> legacy gate -> 0`，没有显式 authority 时保持
  control-neutral；
- Task2 runtime 增加独立 `SafetyProjector` 配置；
- 保留本地 `paths_env` 路径展开与 adapter 日志节流。

新增测试：

- `tools/tests/test_reference_filter_compatibility.py`
- 验证 12 个归档 checkpoint 全部可加载和预测；
- 验证 button Task2 checkpoint 经 worker 处理后 alpha=0、residual=0、command=raw；
- 相关 filter 测试共 26 项通过。

模型归档位置：

```text
artifacts/filter_reference_20260910/checkpoints/
```

当前 Task2 下一步不是直接 active，而是：

```text
兼容性完成
-> 离线比较 6 个 button 模型
-> 确定 fixed/shadow 测试方式
-> 接入 Task2 capture/deployment
-> 真机 shadow 和低权限验证
-> 选定 Task2 filter
```

---

## 6. 推荐的本地部署路线

### Phase 0：代码与 checkpoint 兼容

目标：不接设备，先把代码和 checkpoint 精确对齐。

- 建立 integration branch；
- merge `origin/exp/continuous-filter-backbone-spike`；
- 解决 worker/adapter/config 冲突；
- 保留本地日志节流和路径展开；
- 对 12 个 checkpoint 增加 CPU load smoke test；
- 接受旧 metadata 字段时记录 canonicalized config；
- 不支持 `delta_from_last_executed` 时明确拒绝，而不是用错误 residual 继续运行；
- 给 `zero_initialize_action_head` 增加版本转换或明确的历史兼容规则。

### Phase 1：只读 shadow / 数据链路验证

目标：设备接上后，验证 ROS、相机、state、worker 和 latency，不允许模型改变命令。

- 输出必须严格等于 raw command；
- 记录模型预测作为诊断，不作为 control；
- 检查两路 camera order、JPEG 编码、time sync 和 task profile；
- 测量 GPU 推理和 Unix socket E2E 延迟；
- 检查 worker timeout、stale frame 和 fallback 行为。

归档的 `authority_mode=zero` 模型适合在 Phase 1 验证“模型加载和 TFLOP/latency
链路”，但在此之前必须先解决 loader 兼容问题。

### Phase 2：重新训练 gain-enabled 模型

不能用归档的 action-only checkpoint 冒充 continuous filter。

- Task2：用本地 Task2 成功 episode 重建 filter training view；
- Task3：使用 `Seagate Hub/ICRA2027/task3_Data` 重建 view；
- 训练配置采用 `trajectory_cvae_transformer_v0_2_vlm.yaml`；
- 确认 `gain_enabled=true`、`authority_mode=rate_limited`；
- gain head 和 action head 都进入 checkpoint；
- split 必须按 episode，不能按窗口随机划分；
- 所有 assisted-round target 必须记录 provenance；
- 建议同时训练 deterministic 和 CVAE 作为对照。

### Phase 3：离线验收

必须报告：

- MAE/RMSE/first-step MAE；
- persistence 和 constant-velocity baseline；
- alpha correction/nominal mean；
- alpha variation、AUPRC、interval IoU；
- residual clip、joint limit、velocity limit、fallback；
- latency P50/P95/P99；
- 按 task、episode、operator 分层结果；
- 相机 ablation 和无视觉 baseline。

### Phase 4：真机分阶段验证

顺序必须是：

```text
raw teleoperation
-> shadow prediction
-> alpha = 0
-> very low fixed gain
-> low rate-limited gain
-> full candidate
```

每一阶段都要有人工急停、joint limit、命令速率限制和随时 bypass。未通过前不得把
模型设为默认控制路径。

---

## 7. 需要相关方确认的问题

### 数据与模型

1. 这 12 个 checkpoint 的训练数据是否包含本机当前 Task2/Task3 数据，还是来自另一台机器或合并数据？
2. 是否需要把归档的 action-reference checkpoint 保留为 baseline，还是只保留代码和训练配置？
3. Task1 是否需要重新采集/筛选 correction 段，还是现有 24 个 view 已足够训练？
4. assisted-round 数据的 `expert_action_target_rad` 是否确实来自审计记录，而不是控制器输出？
5. 是否要求同一操作员、同一相机布置和同一 joint direction 才允许迁移模型？

### 代码与兼容性

6. `zero_initialize_action_head` 和 `delta_from_last_executed` 来自哪个未提交代码版本？需要拿到训练时的精确 commit 或转换脚本。
7. runtime 是否统一使用 `predicted_residuals`，还是继续维持“绝对动作减 raw”的合同？
8. worker 在 gain enabled 时应如何组合 `predicted_actions`、baseline 和 alpha？
9. 当前本地“去除 shadow”改动是否保留？如果保留，如何满足论文和真机安全要求的 shadow 预验收？
10. 旧 v0.1 checkpoint 是否必须继续兼容，还是只保留离线转换路径？

### 部署与安全

11. 本机实际使用的相机 serial、topic、分辨率、帧率和 camera order 是什么？
12. right-arm vendor 单位到 filter 坐标变换是否与 `right_arm_vendor_to_filter_v1` 完全一致？
13. 允许的最大 residual、rate、command velocity 和 model age 是否沿用
    `0.01 rad / 0.05 rad/s / 0.5 rad/s / 300 ms`？
14. 5 Hz 推理是否满足采集要求，还是需要提升到 10 Hz？
15. 真机 active 测试由谁负责急停、接管和异常恢复？
16. 是否需要先采集一批 raw-only episode，专门作为新 gain 模型的 local calibration/validation？

---

## 8. 当前建议决策

- **不要直接把归档 `.pt` 接到本机 active command path。**
- **先把分支算法合入，但把归档模型当作 action-reference baseline。**
- **Task2 优先做兼容和 shadow 验证，Task3 随后。**
- **要采集带连续辅助的 Task2/Task3 数据，必须重训 gain-enabled 模型。**
- **Task1 必须单独训练，当前归档没有对应模型。**
- **所有真机测试必须先 shadow、零增益、低增益，再考虑 rate-limited active。**

---

## 9. 相关文件

分支算法与文档：

- `docs/CONTINUOUS_ASSISTANCE_ARCHITECTURE_PLAN.md`
- `docs/ARCHITECTURE.md`
- `src/teleop_filter/trajectory_vae.py`
- `src/teleop_filter/runtime.py`
- `src/teleop_filter/safety.py`
- `tools/learned_filter_worker.py`
- `tools/learned_filter_ros_adapter.py`
- `tools/run_filter_ablations.py`
- `config/filters/trajectory_cvae_transformer_v0_2_vlm.yaml`
- `config/runtime/learned_filter.yaml`

归档证据：

- `artifacts/filter_reference_20260910/README.md`
- `artifacts/filter_reference_20260910/CHECKSUMS.sha256`
- `artifacts/filter_reference_20260910/evidence_freeze.json`

当前本地 task 进展：

- `docs/3个task_filter的实验记录.md`
