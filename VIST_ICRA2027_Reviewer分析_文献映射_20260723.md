---
tags: [VIST, ICRA2027, Reviewer反馈, 文献映射, 团队分工]
created: 2026-07-23
---

# VIST Reviewer 方法论攻击 → 文献映射 → 修改方案

> 本文排除所有 writing/符号/格式 问题，只保留对核心方法论的攻击。
> 每条攻击映射到6篇新论文（及原有文献）中可借鉴的解决方案。
> 最后给出给新人可执行的任务拆分。

---

## 一、方法论层面的 Weakness（排除 writing 后共 11 条）

### W1. α 不是真正的 "意图" — 是启发式增益调度器

**来源**: Reviewer 3, Lines 84-91
**原文**: "The central concept of 'intent' is weakly defined and arguably misleading... functions more as a heuristic gain scheduler than true intent estimation."

### W2. 强依赖已知任务几何（人工标定的 T_target）

**来源**: Reviewer 3, Lines 93-99; Reviewer 4, Lines 160-165
**原文**: "assumes access to a calibrated target pose and predefined task manifold... it is unclear why trajectory planning or standard constraint-based control would not suffice."

### W3. 泛化性局限 — 仅适用于单轴插入任务

**来源**: Reviewer 4, Lines 160-165
**原文**: "How does the approach generalize to a generic assembly task which is not limited to a single-axis insertion?"

### W4. 视觉组件贡献边缘 — 仅用于初始标定，不在控制闭环内

**来源**: AE + Reviewer 3, Lines 109-115
**原文**: "vision is only used for initial pose calibration and is not part of the control loop."

### W5. α 切换时出现突然运动 — 与 "平滑无缝过渡" 声称矛盾

**来源**: Reviewer 4, Lines 173-181
**原文**: "when there is the intervention of the alpha_geo component (at about 30s), this corresponds to a sudden movement... strongly contradicts the author claim that their method ensures a soft and seamless transition."

### W6. 低成本外骨骼的动机论证不充分

**来源**: Reviewer 3, Lines 101-107
**原文**: "does not rigorously argue why this setting is preferable over higher-fidelity systems (e.g., ALOHA) in realistic deployment scenarios."

### W7. 实验结果不完整 — 仅主要反映 0.3mm 实验

**来源**: Reviewer 4, Lines 182-184
**原文**: "What does it mean that the results 'primarily reflect' the 0.3mm experiment? Why are the other experiments not reported?"

### W8. Section V-B 的 claim 不被实验结果支持

**来源**: Reviewer 4, Lines 187-189
**原文**: "The claim written in this text are not supported by the reported results."

### W9. "Probabilistic fusion" 概念解释不清

**来源**: Reviewer 4, Lines 145-147
**原文**: "Why do the authors talk about 'probabilistic fusion'? Are the factors alpha treated as probabilities?"

### W10. "意图保真度" vs "动作保真度" 声称过度

**来源**: Reviewer 3 总体评价 + AE
**原文**: "the results do not support the stated claims" + "overstates its claims and is misleading as to its contribution."

### W11. 实验结果未展示对竞争方法的清晰优势

**来源**: Video comment + Reviewer 3
**原文**: "no clear advantage against the competitors is visible" + "appears just as good/noisy as prior work."

---

## 二、每条 Weakness → 文献映射

### W1: α 是 heuristic → 需要 principled α

| 论文 | 借鉴什么 | 怎么做 |
|------|----------|--------|
| **Güleçyüz (RA-L 2025)** | α = c_A / (c_A + c_H)，c_A 来自 TP-HSMM 状态协方差，c_H 来自遥操作透明度 | 把 VIST 的 α 从几何启发式改为 **置信度驱动**：autonomy confidence（不确定性↓→α↑）+ human confidence（信号质量↓→α↓） |
| **SUBTA (ICRA 2026)** | GNN + dynamic self-attention 从人手位姿预测 task label | 用 learning-based intent predictor 替代手工 α fusion——α 不来自几何，来自 learned task belief |
| **Adaptor (ICRA 2026)** | 噪声注入建模意图不确定性 | α 的学习信号可以直接从意图不确定性导出：uncertainty 高→探索，低→约束 |

### W2: 依赖已知 T_target → 需要从观察学任务流形

| 论文 | 借鉴什么 | 怎么做 |
|------|----------|--------|
| **SUBTA (ICRA 2026)** | Scene graph + graph edit distance 规划目标位姿 | 用 scene graph 做实时目标位姿推理，替代人工标定。对 peg-in-hole: 检测到孔洞→自动生成目标流形 |
| **Adaptor (ICRA 2026)** | VLM 提供视觉上下文 | VLM + 几张 demo 图像 → infer 任务类型和约束区域（"这是 USB 插入任务，目标区域在右上角"） |
| **RINSE (arXiv 2026)** | 平滑度指标 SAL/TED | 用平滑度做自监督——不需要目标位姿，让轨迹自然收敛到高置信度、低抖动的流形 |

### W3: 仅支持单轴插入 → 需要多任务泛化

| 论文 | 借鉴什么 | 怎么做 |
|------|----------|--------|
| **SUBTA (ICRA 2026)** | 9 种 gated motion behaviors，scene graph 处理不同任务类型 | 把 VIST 的 α 框架从 "单一流形约束" 扩展为 "多流形切换"——不同任务对应不同 latent manifold |
| **SAPS (arXiv 2026)** | VLA 做通用策略，不限于特定任务 | 如果 VIST 框架能泛化到 LIBERO-10 等多任务 benchmark，不用限定 peg-in-hole |

### W4: Vision 不在控制环 → 让视觉做实时 confidence signal

| 论文 | 借鉴什么 | 怎么做 |
|------|----------|--------|
| **SUBTA (ICRA 2026)** | 实时 scene graph 参与 motion behavior 选择 | 让视觉在闭环内提供两类信号：(1) 目标位姿估算（online refinement，不是一次性标定）；(2) 操作阶段检测（接近中/接触中/插入中 → 调 α） |
| **SAPS (arXiv 2026)** | VLA 的视觉输入用于 policy steering | 用 pretrained VLM 做视觉 confidence estimator——"我看到孔洞了，置信度高，可以多给自主策略权重" |

### W5: α 切换时 sudden movement → 需要稳定性保证

| 论文 | 借鉴什么 | 怎么做 |
|------|----------|--------|
| **Güleçyüz (RA-L 2025)** | Three-port TDPA-ER | 在 α 切换时加入能量约束——当仲裁权重大幅变化时，TDPA 保证系统不注入过多能量导致抖动 |
| **Jabbour (HAL 2024)** | MPC blending with feasibility guarantee | α 的变化不直接作用于末端，而是通过 MPC 在 receding horizon 上做有约束优化——保证平滑 |

### W6: 低成本动机不充分 → 需要重构动机

| 论文 | 借鉴什么 | 怎么做 |
|------|----------|--------|
| **RINSE (arXiv 2026)** | 数据质量 > 数据数量 —— SAL 过滤用 1/6 数据 +16% 成功率 | 重构 argument：**不是 "因为便宜所以好"，而是 "便宜硬件的噪声可以被算法滤掉，滤掉后的数据和昂贵硬件一样好"** |
| 自身数据 | 旧 paper 已有外骨骼数据 | 做一组对比实验：外骨骼 vs ALOHA 在同一个任务上的 demo 质量 → 证明 VIST 的滤波让外骨骼 demo 达到 ALOHA 级别 |

### W7+W8: 实验结果不完整/不支持 claim → 实验设计

| 论文 | 借鉴什么 | 怎么做 |
|------|----------|--------|
| **Güleçyüz (RA-L 2025)** | 12 人用户研究，完整报告（success rate + trajectory 对比 + NASA-TLX） | 实验报告 checklist：参与者人数+背景、所有实验条件（不只挑最好的）、统计显著性、效应量 |
| **SUBTA (ICRA 2026)** | 多 metric 完整报告 | 每个 claim 至少对应一张表/图；消融实验单独成节 |

### W9: Probabilistic fusion 解释不清 → 需要清晰的概率框架

| 论文 | 借鉴什么 | 怎么做 |
|------|----------|--------|
| **Güleçyüz (RA-L 2025)** | α = c_A/(c_A+c_H) 公式清晰、概率解释明确 | 把 VIST 的 α fusion 写成 **标准贝叶斯融合** 形式：α = P(intent|observation) = P(obs|intent) × P(intent) / P(obs) |
| **Jabbour (HAL 2024)** | AKF 框架的数学定义清晰 | 参考其 AKF 协方差调度的数学表达 |

### W10: Claim 过度 → 需要收紧贡献声明

**策略**：把 "意图保真度 (Intent Fidelity)" 从哲学概念降格为可操作的数学定义——
> "Intent fidelity = the probability that the smoothed trajectory converges to the intended goal under uncertainty."（一个可计算的 metrics，不是一个空洞的概念）

### W11: 对比优势不明显 → 需要更多的对比方法

**必须包含的 baseline（至少 4 个）**：
1. Raw teleop（无滤波）
2. One-Euro Filter（标准去抖）
3. GELLO / ALOHA（高保真基线——如果硬件条件允许）
4. Güleçyüz confidence-based arbitration（**新的必须 baseline**，最直接竞争者）

---

## 三、新 Contribution 的可能方向（按工作量排序）

### C1: Confidence-Driven α（工作量最小，6周可行）
**Claim**: VIST 的 α 从 "几何启发式" 升格为 "置信度驱动贝叶斯融合"
**实验**: peg-in-hole + USB insertion（复用旧平台），加 Güleçyüz baseline
**需要对比的指标**: success rate, smoothness (jerk), completion time, NASA-TLX
**可行性**: 高。不换硬件，不改架构，只改 α 的定义

### C2: Visual Confidence Signal（工作量中等）
**Claim**: 视觉从标定工具升格为实时 confidence estimator，在闭环内提供 task belief
**实验**: 需要验证视觉模块确实提高了 confidence 估计准确性
**可行性**: 中。需要加一个轻量视觉模块（检测孔洞/目标区域）

### C3: Learned Task Manifold（工作量大）
**Claim**: 不需要人工标定 T_target，从 few-shot demos 学习 latent constraint manifold
**实验**: 需要新任务（不只 peg-in-hole），验证 learned manifold 对 unseen 目标的泛化
**可行性**: 低。6周内难以完成数据采集+训练+验证。**建议作为 Discussion 里的 future work 或仅做 proof-of-concept**

### C4: TDPA-Guaranteed Smooth Transition（工作量中等）
**Claim**: α 切换不再产生 sudden movement，引入 energy-based passivity guarantee
**实验**: 复现 Güleçyüz 的 TDPA 思路，在 VIST 的 α 切换点注入能量约束
**可行性**: 中。理论部分可以借鉴 Güleçyüz，不需要从零推导

---

## 四、推荐策略：C1 + C4 + C2 的部分

| 优先级 | Contribution | 工作量 | 理由 |
|--------|-------------|--------|------|
| **必做** | C1: Confidence-Driven α | 最小 | 直接回应 W1，且 Güleçyüz 提供了清晰可复现的方案 |
| **必做** | C4: TDPA-Guaranteed Transition | 中等 | 直接回应 W5（abrupt behavior），Güleçyüz 可直接参考 |
| **加分** | C2: Visual Confidence | 中等（部分） | 回应 W4，但不一定要完整的视觉模块——可以先用 depth camera 做简单的接近度检测 |
| **讨论** | C3: Learned Manifold | 大 | 放在 Discussion/Future Work，不做完整实现 |

**一句话 contribution statement（初稿）**：
> "Unlike Güleçyüz et al. who rely on haptic transparency for human confidence, VIST-C (Confidence-Driven VIST) estimates human confidence from exoskeleton motion consistency and visual task progress, enabling principled α arbitration without force feedback — making shared autonomy accessible on hardware that costs 1/10th of haptic systems."

---

## 五、给新人的可执行任务

### 5.1 两周内需要产出

| 任务 | 负责人 | 产出 | 截止 |
|------|--------|------|------|
| 精读 Güleçyüz Section III-IV | 张博皓 | 一页 summary + 回答三个问题（见下方） | 明天 |
| 精读 SUBTA + Adaptor（核心方法部分） | 录过工资 | 一页 summary + 和我们工作的关联点 | 明天 |
| 精读 Jabbour HAL + RINSE + SAPS | 录过工资 | 核心点整理 + 可借鉴方案 | 后天 |
| 实验环境搭建确认 | 张博皓 | Checklist: 外骨骼能通？ROS2 能通？相机呢？ | 本周 |
| 写完 W1-W11 → 文献 → 方法 → 实验的详细映射表 | 你（review） | 本文档完善 | 后天 |

### 5.2 Güleçyüz 必答三问

1. 他们的 α 从哪两个量算出来的？每个量各用什么 model？  
2. 他们的 TDPA-ER 是怎么保证 α 切换时系统稳定的？（一句话概括原理）  
3. 他们的实验用了什么硬件、什么任务、多少被试？和我们有什么不同？（列一个对比表）

### 5.3 SUBTA + Adaptor 泛读提纲

- 核心方法用了什么架构（不用读推导，读输入/输出/损失函数）  
- 他们怎么定义 "intent"？（一句话）  
- 实验用的什么硬件平台？和我们有什么不同？  
- 和 VIST 最相关的 1-2 个点是什么？我们能直接用吗？还是需要适配？

---

## 六、今晚短会议程（10min）

每人 3 分钟，只讲：
1. **哪条 Weakness** — "我看的是 W1（α 不是真正的 intent）"
2. **哪篇论文** — "Güleçyüz 用 TP-HSMM 协方差做 autonomy confidence"
3. **我们能不能借鉴** — "可以，但我们的外骨骼没有力反馈，不能直接用他们的 human transparency metric，需要用运动一致性替代"
4. **能做到什么程度** — "C1 可以在两周内改完 α 定义，实验沿用旧平台"

**按这个模板：Weakness → 论文 → 方法 → 能做多少 → 需要什么实验 → 结论够不够支撑 claim**

---

## 七、Güleçyüz Section III 完整公式拆解（2026-07-23 精确提取）

### 7.1 核心公式：α 的完整定义

**仲裁公式 (Eq. 11)**：
```
α = c_A / (c_A + c_H)
```

- 当 c_A >> c_H：α → 1，自主策略主导
- 当 c_H >> c_A：α → 0，人类操作主导
- 这是标准贝叶斯融合形式——两个置信度自然地竞争控制权

**c_A 的定义 (Eq. 12)**：自主置信度
```
c_A = (trace(Σ̄) - trace(Σ_t)) / (trace(Σ̄) - trace(Σ̲))
```
- Σ_t：TP-HSMM 当前状态的协方差矩阵
- Σ̲：预设上界（高置信度），Σ̄：预设下界（低置信度）
- 线性归一化到 [0,1]
- 协方差大 → 模型不确定 → c_A 低 → α 小 → 人类主导
- 本质：**aleatoric uncertainty（来自演示噪声和遥操作延迟的可变性）**

**c_H 的定义 (Eq. 13)**：人类置信度
```
c_H = 1 - RATE
```
- RATE ∈ [0,1]：passivity controller 处理的 dissipative energy 与 output energy 的比值
- RATE 高 → controller 干预多 → 透明度低 → 人类置信度低
- RATE 低 → controller 干预少 → 透明度高 → 人类置信度高
- **关键制约**：RATE 必须从 passivity controller 获取，passivity controller 必须有力反馈信号才能工作

### 7.2 意图推断（α 的上游模块）

**目标预测 (Eq. 5)**：
```
G*_t = argmax ∏ P(θ_i|G)
```
延迟感知版本 (Eq. 7)：
```
P(θ_t|G) ∝ exp(-β · Q_G(u_h,t, s_{t-d}))
```
- s_{t-d}：延迟 d 个单位时间的机器人状态（不是当前状态）
- Q_G：余弦距离 (Eq. 8)：`arccos(u_h,t · u_a(s_{t-d}) / ||u_h,t|| ||u_a(s_{t-d})||)`
- 核心 insight：人类基于**延迟的画面**做决策，所以推断意图时要考虑延迟

### 7.3 自主控制力 (Eq. 3)
```
f_a = K^P_z*(y*_t - x_t) + K^V_t · ẋ_t
```
- y*_t：线性二次跟踪生成的平滑吸引子轨迹
- K^P_z*、K^V_t：从 TP-HSMM 每个状态估计的刚度和阻尼矩阵
- 本质：**variable impedance control**——不同任务阶段有不同的刚度和阻尼

### 7.4 三端口 TDPA-ER 稳定性保证

核心公式 (Eq. 14-17)：能量监控单元追踪三端口能量流，当输出超过可用储能时按比例分配 excess power 到 passivity controller 进行阻尼消耗。

- PC1（leader端）：阻抗型阻尼 → 输出力 f_l
- PC2（follower端）：阻抗型阻尼 → 输出力 f_c
- PC3（autonomy端）：导纳型阻尼 → 输出速度 v_f（可能引入位置漂移——这是他们的 limitation）

### 7.5 实验配置

| 项目 | Güleçyüz | VIST (我们) |
|------|----------|------------|
| 机器人 | Franka Emika Panda | ? |
| 人机接口 | **sigma.7 haptic device（有力反馈）** | **外骨骼（无力反馈）** |
| 力传感器 | BotaSys SensONE F/T | 无 |
| 被试 | 12人（5人有经验） | 需补充 |
| 任务 | Frames & Obstacles（多目标避障）+ Rubber Band（力敏感） | Peg-in-hole + USB insertion |
| 延迟 | 100/200/400ms 人工引入 | 无人工延迟（但系统有天然延迟） |
| 条件 | C1(DT) / C2(autonomy-confidence only) / C3(dual-confidence) | Raw / One-Euro / VIST old |
| 自主策略 | TP-HSMM (progressive LfD) | AKF |
| c_H 来源 | passivity controller 的 RATE | **不存在 → 需要替代信号** |

---

## 八、关键洞察：我们的差异化窗口

### 8.1 他们的方法最脆弱的地方

**c_H 完全依赖力反馈。** Eq. (13) 的 RATE 从 passivity controller 获取，passivity controller 监控的是力/能量交互。这意味着：

1. 没有力传感器 → 没有 passivity controller → 没有 RATE → 没有 c_H
2. **任何纯运动学遥操作设备（包括外骨骼、VR手柄、视觉手部追踪）都无法直接使用他们的方法**
3. 他们用的是 sigma.7 haptic device（单价约 $20,000-30,000），我们的外骨骼成本约为其 1/100-1/200

### 8.2 我们的替代方案

**人类置信度 c_H 的三个候选替代信号**（都不需要力传感器）：

1. **运动一致性 (Motion Consistency)**：滑动窗口内手部速度方向的方差。直觉：操作者确定时运动方向一致；抖动/犹豫时方向反复变化。计算：`c_H = 1 - std(velocity_direction[-N:]) / max_std`

2. **速度幅值稳定度 (Speed Stability)**：手部速度大小的变异系数（std/mean）。直觉：精细操作阶段速度自然下降且稳定；探索阶段速度变化大。计算：`c_H = exp(-CV_speed)`

3. **与自主策略的一致性 (Human-Autonomy Agreement)**：直接用 Eq. (8) 的余弦距离，但不通过 Boltzmann rationality，而是作为 c_H 的组成。直觉：当人类操作方向和自主策略方向一致时 → 人类置信度高 → 可以多给自主权重。这个信号 Güleçyüz 用于 intent inference，我们也可以用于 arbitration。

### 8.3 Contribution 重述

**我们现在可以把 contribution 写成针对 Güleçyüz 的精准对标**：

> "While Güleçyüz et al. (RA-L 2025) introduced principled confidence-driven arbitration, their human confidence c_H relies on haptic transparency (RATE from passivity controller), requiring costly force-feedback hardware. VIST-C replaces c_H with **motion-consistency-based human confidence** — computable from any kinematic teleoperation device (exoskeleton, VR controller, camera-based hand tracking) — while maintaining the same dual-confidence arbitration framework. This democratizes principled shared autonomy to hardware costing two orders of magnitude less."

---

## 九、旧数据分析（待做，数据在移动硬盘）

需要验证的关键假设：
1. 新旧数据中，motion_jitter 是否能区分专家和新手？
2. motion_consistency 是否和旧 paper 中 NASA-TLX 的 skill gap 相关？
3. 旧 α 和 motion_consistency 的趋势是否一致？（如果不一致 → 说明启发式 α 确实有问题 → 这本身就是对旧 paper 的一个实证反驳）

**当你拿到移动硬盘后，我可以帮你跑分析脚本。**

---

## 十、今晚短会输出清单（你拿着去开会）

给每人一张表，让他们填空：

| Weakness | 你看的论文 | 方法（一句话） | 我们能借鉴什么 | 需要什么实验验证 | 6周内能做吗 |
|----------|-----------|-------------|--------------|----------------|-----------|
| W1: α heuristic | | | | | |
| W2: 已知 T_target | | | | | |
| W3: 单轴插入 | | | | | |
| W4: 视觉不在环 | | | | | |
| W5: 突然抖动 | | | | | |
| W6: 低成本动机 | | | | | |

你的任务：会前先把 Güleçyüz 对应的行自己填一遍（上面已经给了答案），会上用来对比他们的答案——偏差就是需要讨论的地方。
