# VIST → ICRA 2027 Handoff Document

> 给 AI 助手的快速上手指南。包含项目全部上下文、已完成的决策、待做事项。
> 最后更新：2026-07-23

---

## 1. 项目状态速览

**VIST** — 面向低成本外骨骼遥操作的视觉引导共享控制框架。核心：连续因子 α 动态调度 AKF 协方差，实现自由探索↔流形约束的平滑过渡。

- **投稿目标**：ICRA 2027（ddl 约 2026 年 9 月初，剩余约 6 周）
- **状态**：IROS 2026 被拒，正在改进中
- **团队**：用户 + 两名低年级本科生（张博皓、录过工资）
- **代码/数据**：旧数据在移动硬盘（相机位置已变，需重新采集），代码可能需要重构

**关键约束**：6 周时间、两个新手助手、无 GPU 算力瓶颈（核心改进方向不需要训练模型）、低成本外骨骼硬件（无力反馈）、国内网络（GitHub/arXiv 可能不稳定）

---

## 2. 拒稿核心问题（方法论层面，共 11 条，已排除写作/符号问题）

| ID | Weakness | 严重程度 |
|----|----------|----------|
| W1 | α 不是真正的"意图"——启发式增益调度器，不是意图推断 | 致命 |
| W2 | 强依赖已知任务几何（人工标定 T_target） | 致命 |
| W3 | 仅适用于单轴插入任务，泛化性不足 | 高 |
| W4 | Vision 仅用于初始标定，不在控制闭环内 | 高 |
| W5 | α_geo 介入时出现 sudden movement，与"平滑过渡"claim 矛盾 | 致命 |
| W6 | 低成本外骨骼的动机论证不充分（为什么不用 ALOHA?） | 中 |
| W7 | 实验结果不完整（"primarily reflect 0.3mm experiment"） | 中 |
| W8 | Section V-B claim 不被结果支持 | 中 |
| W9 | "Probabilistic fusion"概念解释不清 | 中 |
| W10 | 声称过度（intent fidelity 概念空洞） | 中 |
| W11 | 相对竞争方法优势不明显 | 高 |

完整分析：`Projects/VIST_ICRA2027_Reviewer分析_文献映射_20260723.md`

---

## 3. 最关键的竞争者：Güleçyüz et al. (RA-L 2025)

**"Enhancing Shared Autonomy in Teleoperation under Network Delay: Transparency- and Confidence-Aware Arbitration"**

### 核心公式（Section III-C）

```
α = c_A / (c_A + c_H)                                    Eq.(11)
c_A = f(trace(Σ_t))                                       Eq.(12) — TP-HSMM 状态协方差归一化
c_H = 1 - RATE                                            Eq.(13) — RATE 来自 passivity controller
f_a = K^P_z*(y*_t - x_t) + K^V_t · ẋ_t                   Eq.(3)  — variable impedance control
```

### 关键洞察：c_H 必须有力反馈

c_H 依赖 passivity controller 的 RATE 值。Passivity controller 监控力/能量交互。**没有力传感器 → 没有 passivity controller → 没有 RATE → 没有 c_H**。

他们用 sigma.7 haptic device（$20K-30K），我们用外骨骼（$100-200）。

**→ 这是我们的差异化窗口：用运动学信号替代力信号来估计 c_H。**

### 实验配置对比

| | Güleçyüz | VIST (我们) |
|---|---|---|
| 机器人 | Franka Emika Panda | 需确认 |
| 人机接口 | sigma.7 haptic device（有力反馈） | 外骨骼（无力反馈） |
| 力传感器 | BotaSys SensONE F/T | 无 |
| 被试 | 12人（5人有经验） | 需补充（≥6，含专家和新手） |
| 任务 | Frames & Obstacles + Rubber Band | Peg-in-hole + USB insertion |
| 条件 | C1(DT) / C2(autonomy-c only) / C3(dual-c) | Raw / One-Euro / VIST old / VIST-C new |
| 自主策略 | TP-HSMM (progressive LfD) | AKF |
| c_H 来源 | passivity controller RATE | **运动一致性（待验证）** |

---

## 4. 已确定的改进方向

### 必做：C1 + C4（6 周内可行）

**C1: Confidence-Driven α 替代启发式 α**
- 新 α = c_A / (c_A + c_H)
- c_A: 模型不确定性（已有 AKF 协方差可用）
- c_H: **运动一致性**（速度方向方差、速度幅值变异系数、或人-自主策略余弦一致性）
- 不换硬件、不改架构、只改 α 的计算方式

**C4: Energy-Bounded α Transition（借鉴 TDPA 思想）**
- 在 α 切换时加入变化率约束
- 保证不产生 Reviewer 4 指出的 "sudden movement"
- 不一定要完整实现三端口 TDPA——可以先做简单的 α 变化率 clip + 阻尼注入

### 加分：C2（部分）

**C2: Visual Confidence Signal**
- 用 depth camera (RealSense D435i) 做实时 task-progress estimation
- 检测"是否接近目标区域"→ 输入 c_A
- 回应 W4（vision 不在控制环）
- 深度取决于实现复杂度——至少可以做 offline analysis

### 放在 Future Work/Discussion

**C3: Learned Task Manifold** — 6 周不够完整实现，仅做 proof-of-concept 或 discussion

---

## 5. 替代 c_H 信号的三个候选（待实验验证）

| 信号 | 计算方式 | 直觉 | 需要验证 |
|------|----------|------|----------|
| 运动一致性 | 滑动窗口内速度方向方差：`c_H = 1 - std(dir[-N:]) / max_std` | 确定时方向一致，犹豫时反复变化 | 能否区分专家/新手？与 NASA-TLX 相关？ |
| 速度稳定度 | 速度幅值变异系数：`c_H = exp(-CV_speed)` | 精细操作时速度下降且稳定 | 和任务阶段的耦合关系 |
| 人-自主策略一致性 | 余弦距离（复用到 α 而非 intent inference）：`c_H = cos(u_h, u_a)` | 方向一致时人类置信度高 | 和旧 α 的一致性如何 |

**当拿到移动硬盘后，可以在旧数据上验证这三个信号的有效性。**

---

## 6. 暂定 Contribution Statement

> "While Güleçyüz et al. (RA-L 2025) introduced principled confidence-driven arbitration, their human confidence c_H relies on haptic transparency (RATE from passivity controller), requiring costly force-feedback hardware. VIST-C replaces c_H with **motion-consistency-based human confidence** — computable from any kinematic teleoperation device — while maintaining the same dual-confidence arbitration framework. We further introduce energy-bounded α transitions to eliminate abrupt behavior during control authority shifts."

**三个 bullet points**：
1. Confidence-driven α from motion consistency（不需要力传感器）
2. Energy-bounded α transition（消除 sudden movement，回应 W5）
3. Vision-in-the-loop confidence（视觉在闭环内提供 task-progress signal，回应 W4）

---

## 7. 文献库速查

### 最相关（已精读/半精读）

| 论文 | 算力需求 | 核心借鉴 | PDF |
|------|----------|----------|-----|
| **Güleçyüz RA-L 2025** | 无 | α = c_A/(c_A+c_H), TDPA-ER | 有 |
| **SUBTA ICRA 2026** | 中（GNN训练，RTX 3080可） | Scene graph 目标位姿规划替代人工标定，9种 motion behaviors | 无(arXiv) |
| **Jabbour HAL 2024** | 无 | MPC blending + AKF 同技术路线 | 无(HAL) |

### 次要相关

| 论文 | 算力需求 | 核心借鉴 |
|------|----------|----------|
| **Adaptor ICRA 2026** | 高（VLM + Flow Matching） | 噪声注入建模意图不确定性 |
| **RINSE arXiv 2026** | 无 | SAL/TED 平滑度指标过滤低质量 demo 数据 |
| **SAPS arXiv 2026** | 高（VLA 推理） | Cosine similarity 动态仲裁 |

所有论文 BibTeX：`Zotero/VIST_ICRA2027_papers_20260719.bib`
JSON 元数据：github `wintermute1895/ICRA2027_TELEOP` 的 `papers.json`

---

## 8. 工具与文件位置

| 工具 | 位置 | 用途 |
|------|------|------|
| Zotero 数据库 | `F:\Obsidian\Zotero\zotero.sqlite` | 论文管理 |
| BibTeX 导入 | `Zotero/VIST_ICRA2027_papers_20260719.bib` | 新论文导入（File→Import） |
| 论文添加脚本 | `~/.claude/scripts/add_to_zotero.py` | `--mode bibtex` 生成 BibTeX，`--mode direct` 写 SQLite |
| GitHub | `github.com/wintermute1895/ICRA2027_TELEOP` (branch: cx/research) | 论文列表 + 分析文档 |
| 文献 JSON | repo 中 `papers.json` | 6 篇新论文完整元数据 |
| 分析文档 | `Projects/VIST_ICRA2027_Reviewer分析_文献映射_20260723.md` | Weakness→文献→方案 完整映射 |
| 旧文献地图 | `Learning/灵巧手语义遥操作-文献地图.md` | 原有 19 篇文献 |
| 拒稿分析 | `Learning/IROS2026拒稿意见.md`, `Learning/IROS2026&ICRA2027交接会议.md` | 原始审稿意见和改进方向 |
| CLAUDE.md | 本目录 `CLAUDE.md` | 项目上下文（AI 助手自动加载） |

---

## 9. 实验设计草案

### 对比条件
1. Raw teleop（无滤波）
2. One-Euro Filter（标准去抖）
3. VIST old（heuristic α）
4. **VIST-C new（confidence-driven α）** ← 核心
5. Güleçyüz α replay（用我们的数据跑他们的 α 公式，如果能复现）

### 任务
- Peg-in-hole（0.3mm clearance）
- USB insertion
- 多轴插入（新增，回应 W3）——如果时间允许

### 被试
≥6 人（3 专家 + 3 新手），每人每条件 10 trials

### 指标
- Success rate
- Completion time
- Trajectory smoothness (jerk)
- Path RMSE
- NASA-TLX

### 消融实验
- c_A 单独 vs c_H 单独 vs c_A+c_H 联合 vs 旧 α

---

## 10. 待做事项（按优先级）

### 本周（7.23-7.27）
- [ ] 旧数据分析：验证 motion_consistency 是否能区分专家/新手（数据在移动硬盘）
- [ ] 阅读 SUBTA Method 部分，提取 scene graph 方案如何替代人工标定 T_target
- [ ] 阅读 Jabbour HAL，确认 AKF+MPC 哪些部分已发表
- [ ] 确定最终 contribution statement（基于昨晚短会反馈）
- [ ] 给两个学生派第二周任务

### 第 2-3 周（7.28-8.10）
- [ ] 实现新 α 公式（改一个函数）
- [ ] 添加 α 变化率约束（TDPA-lite）
- [ ] 重新采集数据（相机标定 + 外骨骼通信确认）
- [ ] 跑完 baseline 实验（条件 1-4）
- [ ] 如果时间允许：加视觉 task-progress estimator

### 第 4 周（8.11-8.17）
- [ ] 消融实验
- [ ] 统计分析
- [ ] 图表制作

### 第 5-6 周（8.18-8.31）
- [ ] 写作
- [ ] 修改
- [ ] 视频制作

---

## 11. 团队分工

| 人 | 角色 | 当前任务 |
|----|------|----------|
| 你 | 决策者 | 定方向、审产出、写核心论证、设计实验 |
| 张博皓 | 实验 + 文献 | 读 Güleçyüz → 对每条 Weakness 找论文方案 |
| 录过工资 | 分析 + 文献 | 读 SUBTA/Adaptor/Jabbour → 提取可借鉴方案 |

**给新人的原则**：给 AI prompt 而不是给任务描述。明确"做到什么程度算做完"。

---

## 12. AI 助手使用提示

**如果你是 Claude Code / AI 助手**，请先阅读：
1. 本文档（你正在读）
2. `CLAUDE.md` — 用户背景和偏好
3. `Projects/VIST_ICRA2027_Reviewer分析_文献映射_20260723.md` — 详细分析

**你可以帮助用户做的事**：
- 从论文中提取关键信息（方法、实验、limitations）并映射到 Weakness
- 设计实验方案、检查实验矩阵的完整性
- 修改 contribution statement 的措辞
- 审阅学生的产出（对比用户预判的答案空间）
- 管理 Zotero 论文（用 `add_to_zotero.py --mode bibtex`）
- 分析旧数据（数据在移动硬盘上，用户会提供路径）
- 将分析结果推送到 GitHub（如果网络允许）

**用户偏好**：
- 中文交流
- 直接、批判性分析，不需要软化诊断
- 用研究者标准而非学生标准
- 不要写多余注释和文档
- 动作驱动——给可执行的具体步骤
