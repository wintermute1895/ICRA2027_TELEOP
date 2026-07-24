---
tags: [VIST, ICRA2027, Reviewer回应, 技术方案, 分层规划]
created: 2026-07-24
status: 会议讨论用
---

# VIST → ICRA 2027：Reviewer 批评逐条回应与技术方案

> 5条核心批评 → 每条的文献支撑 → 改进方案 → 分层时间规划 → 自我反驳与边界条件
> 核心原则：**逻辑链 ≤ 3 层；创新在别人的 limitation 上做；方案必须可分阶段交付**

---

## R1：Intent 概念定义模糊，夸大意图推断效果，仅为启发式增益调度参数

### 原文批评回顾
> "The central concept of 'intent' is weakly defined and arguably misleading... The system assumes a known, fixed goal and does not infer user intent in any meaningful sense... The 'intent factor' primarily reflects proximity and motion alignment, functioning more as a heuristic gain scheduler than true intent estimation."

### 问题的本质

不是 Reviewer 吹毛求疵——α = weighted_sum(α_geo, α_dir, α_vel) 确实不是 intent。意图推断的**最低标准**是：给定观测历史，预测用户的目标状态。我们原来的 α 没有预测任何东西，它只是一个空间关系的即时快照。

### 相关文献中的解决方案

| 来源 | 核心方法 | 意图定义 | 与我们场景的适配性 |
|------|---------|---------|------------------|
| **Güleçyüz et al. (RA-L 2025)** §III-B | Boltzmann rationality model：条件化到 delay-affected state → P(goal | trajectory) | 概率推断——意图 = 目标概率分布 | 高：α = c_A/(c_A+c_H) 给了 α 概率语义 |
| **SUBTA (ICRA 2026)** §III-A | GNN + dynamic self-attention over hand pose sequence → task label prediction | 分类+回归——意图 = (task_type, target_pose) | 中：需要预定义 task taxonomy |
| **Adaptor (ICRA 2026)** §III-B | Intention Expert: 噪声注入 → uncertainty-aware trajectory encoding → Flow Matching → action sequence | 不确定性的轨迹预测——意图 = 未来轨迹分布 | 中：Flow Matching 重，但 uncertainty 思路可复用 |
| **TASC (2025)** §III | Open-vocabulary interaction graph via VLM → task-level intent from motion-only input | 关系推理——意图 = 物体间功能关系 | 低：VLM 太重，但 motion-only 的 idea 成立 |

### 我们的改进方案

**核心逻辑链（3层）：**
```
Layer 1: α 不是 intent → α 是 intent 可信度的决策变量
Layer 2: 可信度来自两个不完美信息源的比较 —— 人类运动可靠性 vs 自主策略不确定性
Layer 3: 比较框架使用概率比 α = P(autonomy_reliable | evidence) / P(human_reliable | evidence)
```

**具体公式重新定义：**
```
α_t = c_A / (c_A + c_H)

c_A = g( trace(Σ_TP-HSMM), uncertainty_vision )
     └── Σ_TP-HSMM: TP-HSMM state covariance (aleatoric uncertainty, from Güleçyüz)
     └── uncertainty_vision: pose estimation confidence (from CAP-VS style confidence-adaptive)

c_H = f( SAL(joint_trajectory), jerk(endeffector), vel_variance, direction_alignment )
     └── SAL: Spectral Arc Length (from RINSE)
     └── jerk: 二阶平滑度指标
     └── vel_variance: 区分"自信移动"和"犹豫探索"
     └── direction_alignment: cos(current_vel, target_direction)
```

**为什么这是 intent 而不是 heuristic：**
1. c_H 的每个分量都有物理含义（不是随意选的）
2. α 有概率解释（Güleçyüz 框架的延伸）
3. c_H 在每个时刻都在"推断"操作员的可靠程度——这是对人状态的隐式推断
4. 框架可以被实验证伪（见分层方案）

### 分层改进方案

| 窗口 | 方案 | 工作量 | 风险 |
|------|------|--------|------|
| **短 (2周)** | 保持 α = weighted_sum 形式，但重新命名和定位：不叫 "intent factor"，叫 "task-aligned assistance level"。在论文中明确说 "We do not claim to infer intent; we estimate the operator's current reliability and task-alignment." | 仅写作改动 | Reviewer 可能认为只是换了名字 |
| **中 (4周)** | 实现 c_H = f(SAL, jerk) + α = c_A/(c_A+c_H) 简版（仅运动学特征 + TP-HSMM covariance，无视觉） | 模型实现 + pilot 数据 | c_H 和 success 的相关性可能不显著 |
| **长 (6周)** | 完整双置信度 + 视觉 uncertainty 融入 c_A + 能量约束 α | 全系统 | 时间紧，风险在于视觉 pipeline |

### 自我反驳与边界条件

**反例 1：新手操作员快速但不稳定地移动**
→ 高 vel (看起来自信) 但低 SAL (很多高频震颤)。我们的 c_H 中 SAL 和 jerk 会自动压低置信度，即使 vel 高。✓

**反例 2：专家缓慢精细微调**
→ 低 vel (看起来犹豫) 但高 SAL (平滑无震颤)。c_H 中 SAL 和方向对齐会支撑高置信度，即使 vel 低。需要实验验证。

**反例 3：操作员突然改变意图（放弃当前目标）**
→ 方向对齐骤变，c_H 骤降，自主策略接管。这实际上是正确的行为——当操作员剧烈改变方向时，原目标的自主引导确实不再可靠。但需要加 α 变化率约束（见 R6 方案）防止突然切换。

**审稿人的可能追问**："c_H 和 c_A 都是 heuristic 选择的特征，凭什么说这是 principled？"
→ 回应：c_A 的两个分量（TP-HSMM covariance + visual uncertainty）都来自已有理论的 uncertainty 度量；c_H 的四个分量来自运动平滑度文献（SAL 来自 RINSE/康复科学，jerk 来自轨迹优化文献）。每个分量的选择有引用支撑。**但必须承认**：分量的权重/融合方式确实需要从数据中学习——这正是 L1 的核心贡献。

---

## R2：算法依赖已知几何结构，泛化通用能力不足

### 原文批评回顾
> "The approach assumes access to a calibrated target pose and predefined task manifold. This significantly limits generality... In such settings, it is unclear why trajectory planning or standard constraint-based control would not suffice."

### 问题的本质

两重批评：①你假设 T_target 已知——那你的方法和传统约束控制有什么区别？②预定义 task manifold 意味着你只能做你见过的任务——泛化能力为零。

### 相关文献中的解决方案

| 来源 | 核心方法 | 如何处理未知几何 | 实验平台 |
|------|---------|----------------|---------|
| **SUBTA (ICRA 2026)** §III-B | Scene graph + graph edit distance → 从对象关系推断目标位姿 | 不需要标定 T_target，但需要预定义 object set 和关系 | VR + 双手力反馈 |
| **TASC (2025)** | Open-vocabulary interaction graph via VLM → 从功能关系推理操作目标 | 不需要标定，不需要预定义 object set | 单臂 + VR |
| **VF Designer (2025)** | CAD mate constraints → virtual fixtures 自动生成 | 从 CAD 自动提取约束，但需要 CAD 模型 | 双边遥操作 |
| **H2R-MRSTA (2025)** | 混合现实 + 数字孪生 → peg insertion 等 primitive skill library | 从 MR demo 学习 skill primitive，泛化到新位置 | UR5 + MR 头显 |
| **AirExo-2 (CoRL 2025)** | 外骨骼 + demonstration adaptor → pseudo-robot demo → RISE-2 policy | 不需要目标位姿，policy 从 demo 学隐式目标 | 低成本外骨骼 |
| **CAP-VS (RA-L 2026)** | Confidence-Adaptive Predictive Visual Servoing | 视觉实时估计目标位姿 + 不确定性 → 不依赖离线标定 | 6-DoF 机械臂 |

### 我们的改进方案

**核心逻辑链（3层）：**
```
Layer 1: 我们承认 T_target 需要已知 → 但 T_target 现在由视觉实时估计，不依赖离线标定
Layer 2: 视觉估计的不确定性融入 c_A → T_target 不确定时自主减弱，人类主导
Layer 3: 任务流形从"人工预定义"改为"从 few-shot demo 中在线提取"
```

**具体方案：**
```
原来: T_target = 离线标定的固定值 (hard assumption)
改为: T_target(t) = visual_pose_estimator(RGB-D_t) + uncertainty(t)
       task_manifold = online_extract(last_K_demos)  ← K=3~5 次最近 demo

当 visual uncertainty 高时 → c_A ↓ → 自主策略减弱
当 demo 覆盖了新的目标区域后 → task manifold 自动扩展
```

### 分层改进方案

| 窗口 | 方案 | 工作量 | 风险 |
|------|------|--------|------|
| **短 (2周)** | 改为 claim "视觉实时估计目标位姿"，不 claim "不需要目标位姿"。用 ArUco/QR marker 做视觉标定（这其实是 VF Designer 的思路——用预定义 marker 替代 CAD） | 仅写作调整 + marker 标定代码 | Reviewer 可能说 marker 也是一种 "known geometry" |
| **中 (4周)** | 实现 lightweight object pose estimation (预训练模型) + uncertainty → c_A。不标定 marker，用 RGB-D 做通用目标位姿估计 | 集成视觉 pipeline | 位姿估计精度在 peg-in-hole 场景可能不够 |
| **长 (6周)** | Few-shot task manifold extraction: 从 3-5 次 demo 中提取 latent constraint manifold (via PCA/autoencoder)，替代人工定义 task manifold | 完整的 L2 实现 | 6 周做不完完整验证 |

### 自我反驳与边界条件

**反例：如果视觉完全看不到目标（严重遮挡），怎么办？**
→ c_A → 0，α → 0，系统退化为纯遥操作。这是 feature 不是 bug——系统在不确定时退回到安全基线。Güleçyüz 的框架在 c_A 低时也是退回到纯遥操作。

**审稿人的可能追问**："如果视觉位姿估计有 5mm 误差，peg-in-hole (tolerance < 1mm) 怎么成功？"
→ 回应：α 框架的优雅之处在于——当 visual uncertainty 高时 c_A 低，自主引导很弱，人类精密控制主导。视觉不是用来直接做精密定位的，视觉是用来告诉系统"我现在距离目标大概多远、我有多确定"——这两个量足以驱动 α。真正的高精度仍然靠人类。

**审稿人的可能追问**："你们的 visual pose estimator 和 existing work 有什么不同？"
→ 回应：我们不做新的 pose estimator——我们用一个 off-the-shelf 的模型（如 FoundationPose），核心贡献在于**如何把 pose estimator 的 uncertainty 映射为自主置信度**。这个映射本身是新的，因为我们连接了两个领域（视觉不确定性 → 共享控制仲裁）。

---

## R3：未论证低成本硬件方案合理性，缺少与 ALOHA 等高保真系统对比

### 原文批评回顾
> "The justification for focusing on low-cost exoskeletons is not fully convincing. While scalability is mentioned, the paper does not rigorously argue why this setting is preferable over higher-fidelity systems (e.g., ALOHA) in realistic deployment scenarios."

### 问题的本质

不是 Reviewer 看不起低成本硬件——是你没有论证**低成本硬件的缺陷如何被你算法补偿**。如果你说"我们便宜"，审稿人说"便宜有什么用，精度不够"。你需要说："我们便宜，精度确实不够，但我们的算法专门补偿了这个不足——这是高保真系统不需要做、也做不到的事情。"

### 相关文献中的支撑

| 来源 | 硬件成本 | 关键发现 |
|------|---------|---------|
| **ALOHA 2** | ~$27-32K | 标准 baseline。unilateral control，无力反馈。需要物理机器人在场。 |
| **AirExo-2 (CoRL 2025)** | 低成本外骨骼 | **在野外采集数据，不需要物理机器人在场**。用 demonstration adaptor 关闭 human→robot 的 domain gap。训练出的 policy 与 teleoperated data 训练的 policy 性能相当或更优。 |
| **HOMIE (2025)** | ~$500 | 同构外骨骼（无需 IK）+ motion glove。完成任务的时间是传统遥操作的一半。 |
| **ALPHA-α (2025)** | ~$8.7K | 比 ALOHA 便宜一半以上。bilateral control 捕获力信息而不需要力传感器。 |
| **Güleçyüz et al. (2025)** | Haptic device + F/T sensor | 需要力传感器来计算 c_H = 1 - RATE。高保真，但硬件门槛高，不可规模化。 |
| **我们的外骨骼** | 低成本，无 F/T sensor | **核心差异：我们用视觉+运动学替代力传感来做 confidence estimation。这在高保真系统上不需要做——他们直接有力和力矩读数。** |

### 我们的改进方案

**核心逻辑链（3层）：**
```
Layer 1: 低成本硬件确实精度不如 ALOHA/力反馈系统 —— 我们承认
Layer 2: 但低成本硬件的缺陷（无反馈、高噪声）正是我们算法的设计目标
Layer 3: 高保真系统可以直接用力/力矩算 confidence → 我们能在无力的条件下算 confidence → 这是他们做不到的
```

**论证结构（用于 intro 和 experiment）：**
1. ALOHA 等系统需要力传感器/高精度编码器 → 不可规模化
2. 外骨骼便宜但缺少力信息 → 传统的 shared control (如 Güleçyüz) 无法在此外骨骼上运行
3. 我们的 α 框架不需要力 → 用运动一致性 + 视觉替代力作为 human confidence 的来源
4. 实验对比：我们的外骨骼 + 新 α vs 纯遥操作外骨骼（baseline）vs 理想条件（simulated force feedback）

### 分层改进方案

| 窗口 | 方案 | 工作量 | 风险 |
|------|------|--------|------|
| **短 (2周)** | 在 intro/motivation 中加一个表格对比 ALOHA / HOMIE / AirExo / Güleçyüz / 我们外骨骼 的成本、精度、力反馈、是否需要物理机器人在场 | 写作 | 仅靠表格辩论可能不够convincing |
| **中 (4周)** | 在 experiment 中加一个对比：simulated force sensor 的 upper bound vs 我们的 motion-only confidence。证明 motion-only 和 force-based 的 c_H 有统计显著的相关性 | 仿真实验 | 相关性可能不够强 |
| **长 (6周)** | 把我们的算法部署在至少两种硬件上（外骨骼 + 仿真 haptic system），证明算法对硬件不可知 | 跨平台实验 | 时间不够 |

### 自我反驳与边界条件

**审稿人的可能追问**："如果力传感器这么便宜（ALPHA-α 整个系统才 $8.7K），为什么不直接用有力传感器的方案？"
→ 回应：ALPHA-α 的力估计用的是 bilateral control + disturbance observer，精度不如直接 F/T sensor。更重要的是——**即使有力信息，如何把力映射为 confidence 仍然是一个 open problem**。Güleçyüz 的 RATE 需要精确的系统动力学模型来计算能量。我们提出的运动一致性方案不依赖任何动力学模型——这是一个独立于成本的贡献。

**审稿人的可能追问**："ALOHA 虽然贵，但已经开源，任何人都可以复制。为什么你们还要做外骨骼？"
→ 回应：ALOHA 需要物理机器人在场才能采集数据（leader-follower 架构）——这限制了数据采集的地点只能是在实验室。AirExo-2 已经证明外骨骼可以在野外采集数据（in-the-wild），我们的方法进一步不需要力传感器——任何人在任何地方用外骨骼采集的数据，经过我们的 shared control 在线优化后，都可以用于下游 IL 训练。

---

## R4：仅单轴验证，未说明多场景拓展通用性

### 原文批评回顾
> "How does the approach generalize to a generic assembly task which is not limited to a single-axis insertion?"

### 问题的本质

我们只在 Z 轴方向验证了 peg-in-hole 和 USB 插入——都是垂直向下的单轴插入。这是一个非常窄的验证范围。审稿人问的不是"你能不能做别的任务"，而是"你的方法本质上是否只适用于单轴插入"——如果是，那 contribution 的 scope 就很有限。

### 相关文献中的解决方案

| 来源 | 验证场景 | 多样性水平 |
|------|---------|-----------|
| **Güleçyüz (2025)** | Frames & Obstacles + Rubber Band | 2 任务 × 多种 goal frame × 多种延迟 × 12 人 |
| **SUBTA (2026)** | 双手装配（多种子任务） | 9 种 gated motion behaviors 覆盖 push/align/insert 等 |
| **VF Designer (2025)** | Peg-in-hole + button press + hinged door | 3 种不同类型任务 × 3 种延迟 × 8 人 |
| **TASC (2025)** | Hammer-hit-nail + Marker-insert-mug + Spoon-scoop-beans 等 | 零样本泛化到多种操作类型 |
| **H2R-MRSTA (2025)** | Peg insertion + gear meshing + nut fastening + disassembly | 6 种工业装配任务 |
| **Adaptor (2026)** | 6 种操作任务 | 跨操作员 + 跨任务 |

### 我们的改进方案

**核心逻辑链（3层）：**
```
Layer 1: 原方法只适用于单轴插入 → 因为 α_geo 的 task manifold 定义在单个轴向上
Layer 2: 新的 α = c_A/(c_A+c_H) 不依赖 task manifold 的方向 → 适用于任意方向的约束
Layer 3: 验证从 2 任务扩展到 4+ 任务，覆盖不同 insertion direction 和非插入操作
```

**至少要加的实验场景：**
1. **斜角插入**（30° / 45° / 60°）：证明方法不限于垂直插入
2. **水平/侧向插入**（如插拔电源线）：证明方法不限于 Z 轴
3. **非插入操作**（如擦拭桌面——添加平面约束）：证明方法可以 generalize 到非插入约束
4. **自由空间 reaching + 精密插入**（连续任务）：证明 α 在任务阶段切换时平滑过渡

### 分层改进方案

| 窗口 | 方案 | 工作量 | 风险 |
|------|------|--------|------|
| **短 (2周)** | 加 1-2 个新场景的实验数据。在实验板上加斜角 hole + 水平 slot。不需要完整的用户研究，pilot 数据即可证明方法可行 | 实验板改装 + 采集 | Pilot 数据可能不够 statistically significant |
| **中 (4周)** | 3-4 个场景 × 每种场景至少 3-5 人。用新 α 框架统一处理不同的约束方向 | 完整实验 | 需要制作新的实验板/夹具 |
| **长 (6周)** | 4+ 场景 × 8-10 人用户研究 × 跨场景泛化分析。这是对标 Güleçyüz (2 tasks × 12 participants) 和 SUBTA (多种子任务 × 12人) 的水平 | 完整用户研究 | 时间极紧 |

### 自我反驳与边界条件

**审稿人的可能追问**："你们的框架如何处理旋转约束？比如拧螺丝需要特定的旋转轨迹？"
→ 回应（诚实）：我们的当前框架专注于**平移约束**。旋转约束可以加入（在 SE(3) 上定义 task manifold），但这不是当前版本的 scope。在 limitation 中坦诚说明，在 future work 中提及。**但必须强调**：平移约束覆盖了 peg-in-hole, USB insertion, connector mating, drawer opening/closing 等大量实际装配任务——不是 niche。

**审稿人的可能追问**："多场景的 α 行为是否一致？c_H 的特征在不同任务中是否 stable？"
→ 回应：运动一致性特征（SAL, jerk, vel_var）是 task-agnostic 的——它们只依赖操作员的运动特征，不依赖任务定义。这正是我们和 Güleçyüz 的一个重要差异：他们的 c_H 依赖任务特定的 passivity 计算，我们的 c_H 可以跨任务一致地工作。

---

## R5（原 R6）：视觉模块作用过度夸大，未客观说明局限性

### 原文批评回顾
> "The system is described as 'vision-guided,' yet vision is only used for initial pose calibration and is not part of the control loop. There is no real-time perception, tracking, or visual feedback integration. This makes the framing somewhat misleading."

### 问题的本质

这是 AE 也点名的问题——你的标题说 "vision-guided"，但视觉只做了一次性标定。这在 2026 年的 robotics 领域是不可接受的。审稿人不是在说"你要做 SOTA 视觉"——他们在说"如果你声称视觉是核心组件，视觉应该做什么事情在闭环内"。

### 相关文献中的解决方案

| 来源 | 视觉的角色 | 视觉是否在闭环内 |
|------|---------|----------------|
| **CAP-VS (RA-L 2026)** | Confidence-Adaptive Kalman Filter: 视觉 confidence → 动态调节滤波器融合权重 | **是**——视觉 confidence 直接影响控制 |
| **TASC (2025)** | VLM 实时构建 interaction graph → 驱动任务级共享控制 | **是**——视觉 language model 确定 task |
| **AssistDLO (2026)** | Multi-view state estimation → Control Barrier Function 的动态约束 | **是**——视觉状态估计直接进入控制器 |
| **BVCFF (2026)** | Uncertainty-Aware Adaptive Fusion: visual entropy → 动态平衡视觉 vs 控制的权重 | **是**——视觉熵直接影响融合权重 |
| **Güleçyüz (2025)** | Video feed to human operator (for teleop viewing) | **否**——视觉不在算法环路内，但也没声称在 |
| **H2R-MRSTA (2025)** | MR 头显提供操作员的视觉引导 + 数字孪生 | 半——视觉在 human side，不在 robot control loop |

### 我们的改进方案

**核心逻辑链（3层）：**
```
Layer 1: 原来视觉只做初始标定 → 视觉不在闭环内
Layer 2: 现在视觉做两件事: (a) 目标位姿实时估计 (b) 位姿不确定性的实时估计
Layer 3: 视觉不确定性直接影响 c_A → c_A 影响 α → α 影响控制输出 → 视觉在闭环内
```

**视觉在闭环内的具体路径：**
```
RGB-D(t) → visual_pose_estimator → (T_target_est, uncertainty)
                                    ├── T_target_est → task manifold definition → c_A_geometry
                                    └── uncertainty → c_A_vision
                                                      ↓
                                    c_A = g(cov_TP-HSMM, c_A_vision)
                                                      ↓
                                    α = c_A/(c_A+c_H) → AKF Q/R → robot control
```

### 分层改进方案

| 窗口 | 方案 | 工作量 | 风险 |
|------|------|--------|------|
| **短 (2周)** | 去掉 "vision-guided" 的声称，改为承认视觉做了标定。但同时论证：标定不是我们 contribution 的核心，核心是 α 框架。视觉角色弱化为 "experiment setup" | 写作调整 | 审稿人可能仍然觉得 misleading（因为 IROS 版本已经这样声称过了） |
| **中 (4周)** | 加入视觉闭环：用 ArUco/AprilTag 做目标位姿实时跟踪 + detection confidence → c_A_vision。视觉实时参与 c_A 的计算 | 视觉 pipeline 集成 | Marker-based 方法可能被说是 "cheating" |
| **长 (6周)** | 无 marker 的通用目标位姿估计 + uncertainty estimation（如 FoundationPose + MC Dropout ensemble）→ 视觉闭环 + 无 marker 泛化 | 完整的 visual uncertainty pipeline | 视觉推理速度可能不够实时（< 80Hz） |

### 自我反驳与边界条件

**审稿人的可能追问**："如果视觉在闭环内，实时性怎么保证？你们的视觉 pipeline 多少 Hz？"
→ 回应：视觉推理不需要在 80Hz。我们的方案是异步的——视觉在 10-20Hz 更新 c_A_vision，c_A_vision 在两次视觉更新之间用 TP-HSMM 的 c_A 做插值。这个异步架构是关键设计：视觉提供慢但信息丰富的 confidence estimate，TP-HSMM 提供快但信息有限的 confidence estimate，两者互补。

**审稿人的可能追问**："你的视觉不确定性度量什么？怎么验证这个不确定性度量的准确性？"
→ 回应：可以通过实验验证——在不同光照/遮挡条件下计算 visual uncertainty，然后和实际的位姿估计误差做相关性分析。如果 uncertainty 和 error 强相关，就证明我们的 uncertainty 度量是有意义的。

**自我反问**：如果我们的核心贡献是 α 框架，为什么要花大力气做视觉？会不会变成 "also did some vision work"？
→ **关键认知**：视觉不是我们贡献的核心——视觉是**让 α 框架完整的必要组件**。没有闭环的视觉 confidence，α 就退化回 heuristic gain scheduler。视觉 confidence 是在闭环内提供"这次 visual measurement 有多可靠"的量——这个量是 c_A 的一个不可或缺的分量。

---

## 汇总：5条批评的交叉关系与共同方案

### 共享的技术模块

所有 5 条批评的解决方案共享以下技术模块：

```
            ┌─────────────────────────────┐
            │     Visual Pose + Uncert     │ ← 涉及 R2(几何), R5(视觉闭环)
            │     (10-20Hz, async)         │
            └──────────────┬──────────────┘
                           │ c_A_vision
            ┌──────────────▼──────────────┐
            │   TP-HSMM + covariance      │ ← 涉及 R1(intent)
            │   (80Hz, state-dependent)    │
            └──────────────┬──────────────┘
                           │ c_A_tphsmm
            ┌──────────────▼──────────────┐
            │  c_A = g(cov, uncert_vis)   │ ← α 融合框架
            └──────────────┬──────────────┘
                           │
            ┌──────────────▼──────────────┐
            │  c_H = f(SAL,jerk,vel,dir)  │ ← 涉及 R1(intent), R3(低成本)
            │  (80Hz, kinematics-based)    │
            └──────────────┬──────────────┘
                           │
            ┌──────────────▼──────────────┐
            │  α = c_A/(c_A+c_H)           │ ← 涉及 R1, R6(平滑约束)
            │  + Lyapunov-bounded Δα       │
            └──────────────┬──────────────┘
                           │
            ┌──────────────▼──────────────┐
            │  AKF: Q=Q0(1-α), R=R0(α)    │ ← 涉及 R4(多场景)
            │  → robot joint commands      │
            └─────────────────────────────┘
```

### 分层交付路线图

```
Week 1-2 [SHORT — 可提交但弱]:
  - R1: 重命名 α, 定位为 "task-aligned assistance level"
  - R2: 用 ArUco marker 做目标位姿估计，承认需要 marker
  - R3: Intro 加硬件对比表 (ALOHA/HOMIE/AirExo vs 我们)
  - R4: 加 1 个新场景 (斜角插入) pilot 数据
  - R5: 视觉从 "vision-guided" 改为 "vision-assisted"，加 marker tracking

Week 3-4 [MEDIUM — 可提交，有实质改进]:
  - R1: c_H = f(SAL, jerk, vel_var) 实现 + α = c_A/(c_A+c_H)
  - R2: 视觉 uncertainty → c_A_vision
  - R3: 仿真 force-based c_H vs motion-based c_H 相关性实验
  - R4: 3-4 场景 × 3-5 人 experiment
  - R5: 视觉闭环 (marker-based pose tracking + confidence)

Week 5-6 [LONG — 强提交]:
  - R1: 完整双置信度 + 能量约束 α
  - R2: Few-shot task manifold extraction (PCA/autoencoder)
  - R3: 跨平台实验 (外骨骼 + simulated haptic)
  - R4: 4+ 场景 × 8-10 人用户研究
  - R5: Markerless visual pose + MC Dropout uncertainty
```

### 三条必须守住的红线

1. **α = c_A/(c_A+c_H) 必须有概率语义** — 这是区分"heuristic gain scheduler"和"principled arbitration"的唯一标准。如果时间不够，宁可只做 c_H 的简单版本（只用 SAL），也不能回到 weighted_sum。
2. **视觉必须进入控制闭环** — 可以是简单的 marker tracking + detection confidence。不在闭环内的"vision-guided"不会再被接受。
3. **必须有多于一个场景的验证** — 至少 2 个任务（不同插入方向）。只有单轴插入的 paper 没有资格 claim "generic assembly"。
