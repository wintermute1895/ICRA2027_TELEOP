## Abstract
真实机器人数据的瓶颈不仅在于数量，也在于示教轨迹是否有效、可审计并且对下游策略有用。对于需要局部对准、微调或短程执行的视觉可观测任务，操作者可能在同一条轨迹中经历一次性完成、短暂停滞和局部纠正等不同行为；简单地保留所有轨迹或逐帧构造动作标签，都会丢失这些差异。本文提出一种面向遥操作数据采集的视觉条件化动作辅助方法。系统以同构遥操作接口采集原始命令、机器人状态和多视角图像，由人工在冷启动阶段标记纠正区间，并使用冻结的视觉编码器和离线视觉语言模型生成任务阶段与进度审计信号。一个因果 CVAE--Transformer 根据视觉历史和动作历史预测专家动作分布及纠正门控概率，再以有界残差形式辅助操作者输入。该方法不假设逐帧 residual 真值，也不将视觉模型作为动作策略，而是学习“何时应少干预、何时应进行局部纠正”。在真实机器人上，我们评估动作质量、纠正区间识别、单位操作者时间的合格示教产率以及下游模仿学习效用，并通过跨任务、跨配置和跨轮数据隔离检验数据飞轮是否能够稳定改进采集过程。

## 1. Introduction
具身策略的训练正在从“是否有数据”转向“数据是否值得用于训练”。仿真、UMI、第一视角和大规模遥操作数据扩大了数据来源，但真实执行中的时间同步、任务阶段、人工接管和失败原因仍常常没有被记录。对于视觉可观测而动作公差有限的操作，少量错误对齐、停滞或反复尝试会显著降低示教的可复用性；另一方面，专家轨迹并不意味着每一步都需要辅助，真正有价值的数据同时包含平滑的一次性完成轨迹和在困难状态下及时恢复的局部纠正。

现有工作分别研究了遥操作接口、离线数据筛选、视觉轨迹审计、共享控制和交互式模仿学习，但这些模块通常在采集后评价数据，或直接优化部署策略。我们研究一个更窄、可验证的问题：在固定操作者时间和安全边界下，能否利用带审计信息的历史示教，学习一个视觉条件化、因果且有界的动作辅助器，使下一轮遥操作获得更多 task-valid demonstrations，同时在正常阶段保持操作者的原始动作？

本文的核心思想是将纠正区间作为弱监督，而不是人为定义逐帧 residual 标签。操作者或审计员只需标记纠正开始和结束；区间内的同步轨迹提供专家修正行为，区间外的一次性成功轨迹则约束模型不要无谓干预。冻结的视觉编码器提供连续观测，视觉语言模型只在离线阶段提供阶段、进度、停滞和恢复等带置信度的审计候选。模型学习后，以门控残差形式接入真实控制链路，执行本身产生下一时刻的新视觉观测，构成可审计的数据采集飞轮。

我们的贡献如下：

1. 提出一套面向视觉可观测、局部精细操作的可审计示教协议，将原始命令、执行状态、视觉观测和纠正区间统一记录，并把训练用的 A_action 与失败/异常分析用的 A_audit 分离。
2. 提出视觉条件化的 correction-aware CVAE--Transformer。它联合预测专家动作分布和纠正门控概率，以区间弱监督学习何时以及以多大幅度辅助操作者，而不依赖逐帧 residual ground truth。
3. 在真实机器人采集闭环中验证该方法对动作平滑性、纠正时机、合格示教产率和下游策略效用的影响，并通过独立审计集和跨轮隔离分析避免自我强化造成的虚假改进。

## 2. Related Work

### 2.1 遥操作示教与共享自主采集

GELLO、ALOHA、UMI、Mobile ALOHA 和 DROID 分别代表关节映射、主从同构、手持重定向、全身遥操作和跨场景真实数据采集等范式。它们降低了真机示教的硬件和操作门槛，却通常把操作者输入视为最终动作，不研究如何在采集过程中识别并修正局部困难。共享自主和 shared-control 工作表明，人类输入可以与机器人策略融合以降低控制负担。本文沿用现有遥操作接口，研究的是其上的数据采集辅助闭环，而不是新的硬件或完整自主策略。

### 2.2 机器人示教数据质量、数据筛选与视觉审计

Robot Data Curation with Mutual Information Estimators、RINSE 和 RoboMimic 等工作说明，示教轨迹的可预测性、平滑性、覆盖度及其与下游策略的关系可以用于离线筛选。SuccessVQA、AHA 和 RoboReward 则表明视觉模型能够判断成功/失败、进度或奖励，并为缺少密集标签的轨迹提供弱监督。与这些采集后评价或奖励建模方法不同，本文把审计信号作为视觉条件输入和纠正区间提议，进一步影响下一轮真实遥操作；所有自动标签都经过独立人工抽检，且不把 VLM 输出当作动作真值。

### 2.3 学习型共享控制、残差策略与动作纠正

Residual Reinforcement Learning、Residual Policy Learning、HIL-SERL、learning-from-corrections 和 FlowCorrect 等工作利用人类介入或基策略上的残差改善控制性能。本文借鉴“保留已有控制能力、只学习局部修正”的思想，但目标不同：残差不是独立的任务策略，而是由视觉和历史动作共同决定、受门控和安全投影约束的采集辅助信号。一次性成功的轨迹用于抑制不必要的修正，纠正区间用于学习困难状态下的局部替代动作。

### 2.4 交互式模仿学习与持续数据采集闭环

DAgger、ThriftyDAgger、Robot Learning on the Job、IBRL 及相关 intervention-based learning 工作通过专家查询、人工接管或部署中持续收集数据缓解分布偏移。这些方法通常以策略成功率、专家查询次数或部署性能为主要目标。本文将闭环目标定义为数据层面的量：在固定操作者时间、reset 数、配置配额和安全预算下，后续采集得到的 A_action episode 数是否增加。下游 ACT 或 Diffusion Policy 的成功率只作为独立的数据效用验证，不参与训练数据准入。

## 3. Method

### 3.1 Task Formulation and Auditable Data Protocol
我们研究一类视觉可观测、物体已经被抓持、目标或任务状态在相机中可见且需要局部轨迹对齐或微调的操作。一个 episode 可抽象为

$$\tau=\{(o_t,u^{\rm raw}_t,u^{\rm exec}_t,q_t,e_t)\}_{t=1}^{T},$$

其中 $o_t$ 是多相机观测，$u^{\rm raw}_t$ 是操作者命令，$u^{\rm exec}_t$ 是实际执行命令，$q_t$ 是机器人状态，$e_t$ 是带时间戳的审计事件。任务阶段可用接近、对齐、局部纠正和短程执行/完成等粗粒度状态描述；具体位置公差、速度上限和成功判据在每个实验配置中预先声明。抓取本身、长时程导航、依赖不可观测力/力矩的控制、严重持续遮挡和柔性物体动力学不在本文范围内。

操作者只标记纠正区间 $I_k=[t^k_s,t^k_e]$，而不标记逐帧 residual 真值。令 $m_t=\mathbf{1}[t\in\cup_k I_k]$。终止成功、失败、安全中止、人工接管和配置元数据组成数据契约。通过一致性检查的成功且可复用片段进入 $A_{\rm action}$；失败、冲突和异常片段保留在 $A_{\rm audit}$，用于审计和负例分析，不直接作为正向动作目标。数据流为 raw rosbag $\rightarrow$ canonical episode $\rightarrow$ 人工/VLM 审计 $\rightarrow$ correction-aware training view $\rightarrow$ 真实采集闭环。
### 3.2 Vision-Language-Conditioned Correction-Aware Filter
在时刻 $t$，模型读取过去 $L$ 个时刻的命令、状态和视觉表示：

$$x_t=\{u^{\rm raw}_{t-L:t-1},q_{t-L:t-1},v_{t-L:t}\},\qquad v_t=E_{\rm vis}(o_t).$$

本文使用冻结的 SigLIP2 产生连续视觉 embedding；Qwen-VL 仅在离线审计阶段对较长时间片段提出阶段、进度、停滞、恢复和纠正候选，并附带置信度。视觉语言模型不输出动作，也不被当作动作 oracle。

命令、状态和视觉 token 经线性投影后输入因果 Transformer，再由条件 VAE 表征动作分布。解码器输出专家动作预测 $\hat u^{\rm exp}_t$ 和纠正门控概率 $p_t=\Pr(m_t=1\mid x_t)$。部署时的残差是组合定义，而非监督标签：

$$\hat\delta_t=\hat u^{\rm exp}_t-u^{\rm raw}_t,\qquad u^{\rm out}_t=\Pi_{\rm safe}(u^{\rm raw}_t+\alpha p_t\hat\delta_t).$$

其中 $\alpha$ 为实验中固定或受控调节的辅助强度，$\Pi_{\rm safe}$ 投影到关节位置、速度和变化率约束内。因果注意力使用 $M_{ij}=0$（$j\le i$），否则为 $-\infty$，保证在线推理不读取未来观测。真实执行改变下一时刻的观测，因此滤波器每一步都在新的视觉历史上闭环运行。
### 3.3 Corrective Supervision and Offline Training
纠正监督来自同步轨迹与区间标签，而非人为指定 residual。令 $u^{\rm exp}_t$ 表示审计通过片段中的专家动作记录，训练目标为

$$\mathcal L=\lambda_a\mathcal L_{\rm act}+\lambda_g\mathcal L_{\rm gate}+\lambda_n\mathcal L_{\rm nominal}+\beta\mathcal L_{\rm KL}+\lambda_s\mathcal L_{\rm smooth}.$$

动作项采用区间加权：

$$\mathcal L_{\rm act}=\frac1T\sum_t w_t\|\hat u^{\rm exp}_t-u^{\rm exp}_t\|_1,\quad w_t=1+(w_{\rm corr}-1)m_t.$$

门控项为 $\mathcal L_{\rm gate}=\mathrm{BCE}(p_t,m_t)$；名义项约束非纠正阶段少干预，$\mathcal L_{\rm nominal}=T^{-1}\sum_t(1-m_t)\|\hat\delta_t\|_1$。KL 项是 CVAE 条件先验与后验之间的散度，平滑项抑制输出的高频变化。第一轮使用人工确认的 cold-start 数据；Qwen-VL 候选标签必须经过人工抽检，synthetic_smoke_only 数据只能用于链路测试。按 episode 和场景配置划分 train/validation/test，保留固定的人工 held-out audit set，并在每轮冻结该集合以检测自我强化。
### 3.4 Safe Iterative Data Collection
训练后的模型在真实采集时只运行视觉编码器和滤波器，不依赖在线 VLM 生成标签。控制链路为 $o_t\rightarrow E_{\rm vis}\rightarrow f_\theta(x_t)\rightarrow\Pi_{\rm safe}\rightarrow u^{\rm out}_t\rightarrow o_{t+1}$。安全层检查 NaN/Inf、残差幅度和变化率、关节/速度限位、模型超时及视觉缺帧，并提供人工旁路和硬件急停。第 $r$ 轮数据 $D_r$ 训练得到 $f_r$，随后在固定操作者预算下采集并审计形成 $D_{r+1}$：$D_r\xrightarrow{train}f_r\xrightarrow{real\ collection}D'_r\xrightarrow{audit}D_{r+1}$。飞轮结果以 $A_{\rm action}$ episode/操作者分钟数及其质量为主，而不是训练集重构误差。

## 4. Experiments

实验围绕四个问题展开：

1. 纠正区间弱监督能否使模型在正常阶段少干预、在困难阶段及时提供有效辅助？
2. 视觉条件化滤波器能否跨任务和场景配置保持有效，而不是只记忆单一轨迹？
3. VLM 候选审计与人工抽检能否可靠识别阶段、进度和纠正区间，并避免跨轮自我强化？
4. 在固定操作者时间、reset 数、配置配额和安全预算下，飞轮能否提高 A_action 产率并改善下游策略？

### 4.1 Setup and Data Protocol

我们报告机器人、同构遥操作臂、双相机、手部控制器、控制频率、视觉频率、时间同步方式、训练硬件和软件版本。每条 episode 保存 raw/filtered/executed command、机器人状态、RGB 帧、审计事件、纠正区间、终止状态和配置元数据。任务按“接近--对齐--局部纠正--短程执行/完成”的共同结构组织，具体任务、物体姿态和容差在表格中预先声明。冷启动仅使用人工审计的 A_action；失败和冲突事件进入 A_audit。

### 4.2 Correction-Aware Action Assistance

比较 raw teleoperation、1-Euro 或固定时序滤波、trajectory-only 模型、无门控视觉模型和完整视觉条件化模型。报告动作误差、纠正门控 precision/recall/F1、纠正区间 IoU、轨迹速度/加速度/jerk、残差幅度、延迟、裁剪和旁路次数。核心分析区分“一次性成功”与“包含纠正区间”的轨迹，检验模型是否只在需要时提供辅助。消融包括去掉视觉 embedding、去掉 gate、nominal-only、correction-only、不同 $\alpha$ 和不同纠正损失权重。

### 4.3 VLM Audit and Cross-Round Validation

在固定人工 held-out 集合上评估 VLM 的阶段分类、success/failure agreement、纠正 active F1、start/end 时间误差、区间 IoU、置信度校准和人工复核时间。比较人工全量标注、VLM 候选加抽检和不同窗口长度/提示策略。每轮只允许通过独立审计的样本进入训练，并报告审计冲突率、自动标签接受率和 held-out 性能变化；VLM 不得审核由自身标签生成的训练标签。

### 4.4 Data-Collection Efficiency and Downstream Utility

在相同操作者、时间、reset 和场景配置预算下，比较各方法获得的 A_action episode/操作者分钟数、全尝试成功率、安全事件、配置覆盖和轨迹冗余。对每一轮冻结数据训练相同配置的 ACT 或 Diffusion Policy，在未见 episode/configuration 上报告成功率、收敛速度和数据规模曲线。主要对照为 static filter 与 iterative flywheel；下游策略结果只用于独立效用验证，不参与数据准入。失败、near-miss 和恢复片段作为 A_audit 负例进行单独分析，不直接混入正向动作目标。



## 5. Limitations and Conclusion

本文仍有几个明确限制。首先，冷启动依赖少量人工审计，纠正区间边界存在反应延迟和主观差异；VLM 标签需要抽检，尚不能视为无人工成本的真值。其次，当前验证集中在关节编码器遥操作和视觉可观测局部操作，尚不能推出对 VR、IK 重定向、未知遮挡、力控或柔性物体的泛化。再次，残差幅度、门控阈值和安全边界仍需要按任务配置，跨 embodiment 的统一动作语义尚未解决。最后，ACT/DP 的下游提升只能说明数据效用，不能证明对所有 VLA 架构同样成立。

在这些边界内，本文验证了一个可落地的闭环：用人工纠正区间和同步轨迹构造弱监督，用视觉表征理解任务上下文，用因果、门控且安全投影的动作辅助器改善真实采集，再用独立审计集和固定预算评估下一轮数据产率。该框架为研究“如何以更少操作者时间获得更多可训练真机数据”提供了一个可复现实验对象。

## References

参考文献

### A. 遥操作示教、数据集与跨 embodiment 对齐

- [GELLO] Ji, Y. *et al.* “GELLO: A General, Low-Cost, and Intuitive Teleoperation Framework for Robot Manipulators.” *IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)*, 2024. DOI: [10.1109/IROS58592.2024.10801581](https://doi.org/10.1109/IROS58592.2024.10801581).
- [ACT] Zhao, T. Z. *et al.* “Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware.” *Robotics: Science and Systems XIX (RSS)*, 2023. DOI: [10.15607/RSS.2023.XIX.016](https://doi.org/10.15607/RSS.2023.XIX.016).
- [UMI] Chi, C. *et al.* “Universal Manipulation Interface: In-The-Wild Robot Teaching Without In-The-Wild Robots.” *Robotics: Science and Systems XX (RSS)*, 2024. DOI: [10.15607/RSS.2024.XX.045](https://doi.org/10.15607/RSS.2024.XX.045).
- [DROID] Khazatsky, A. *et al.* “DROID: A Large-Scale In-The-Wild Robot Manipulation Dataset.” *Robotics: Science and Systems XX (RSS)*, 2024. 正式 proceedings 页面：[RSS 2024 Proceedings](https://roboticsproceedings.org/rss20/).导入前在页面以题名核对 DOI。
- [Open X-Embodiment] Open X-Embodiment Collaboration. “Open X-Embodiment: Robotic Learning Datasets and RT-X Models.” *Conference on Robot Learning (CoRL)*, 2023; *Proceedings of Machine Learning Research*, vol. 229, 2024. 正式 proceedings：[PMLR 229](https://proceedings.mlr.press/v229/).
- [Octo] Octo Model Team. “Octo: An Open-Source Generalist Robot Policy.” *Robotics: Science and Systems XX (RSS)*, 2024. 正式 proceedings：[RSS 2024 Proceedings](https://roboticsproceedings.org/rss20/).
- [Mobile ALOHA] Fu, Z. *et al.* “Mobile ALOHA: Learning Bimanual Mobile Manipulation with Low-Cost Whole-Body Teleoperation.” 正式发表信息与 DOI 在导入前需从作者项目或会议 proceedings 复核；不要以 arXiv 条目代替最终出版条目。

### B. 行为克隆与交互式数据采集

- [Diffusion Policy] Chi, C. *et al.* “Diffusion Policy: Visuomotor Policy Learning via Action Diffusion.” *Robotics: Science and Systems XIX (RSS)*, 2023. DOI: [10.15607/RSS.2023.XIX.026](https://doi.org/10.15607/RSS.2023.XIX.026). 扩展期刊版：*The International Journal of Robotics Research*, 2025. DOI: [10.1177/02783649241273668](https://doi.org/10.1177/02783649241273668).
- [DAgger] Ross, S., Gordon, G., and Bagnell, D. “A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning.” *Proceedings of the 14th International Conference on Artificial Intelligence and Statistics (AISTATS)*, 2011, pp. 627–635. 正式 proceedings：[PMLR 15](https://proceedings.mlr.press/v15/ross11a.html).
- [ThriftyDAgger] Hoque, R. *et al.* “ThriftyDAgger: Budget-Aware Imitation Learning.” *Conference on Robot Learning (CoRL)*, 2021; *Proceedings of Machine Learning Research*, vol. 164, 2022. 正式 proceedings：[PMLR 164](https://proceedings.mlr.press/v164/).
- [Robot Learning on the Job] Mandlekar, A. *et al.* “Robot Learning on the Job: Human-in-the-Loop Autonomy and Learning During Deployment.” *Robotics: Science and Systems XIX (RSS)*, 2023. DOI: [10.15607/RSS.2023.XIX.005](https://doi.org/10.15607/RSS.2023.XIX.005). 期刊扩展版：*The International Journal of Robotics Research*, 2025. DOI: [10.1177/02783649241273901](https://doi.org/10.1177/02783649241273901).
- [HIL-SERL] Luo, J. *et al.* “HIL-SERL: Human-in-the-Loop Reinforcement Learning for Robot Manipulation.” *Conference on Robot Learning (CoRL)*, 2024. 从正式 CoRL proceedings 导入；其关注人工介入的 residual RL，而非本文的示教采集过滤。

### C. 学习型共享控制、残差与数据质量

- [Residual RL] Johannink, T. *et al.* “Residual Reinforcement Learning for Robot Control.” *IEEE International Conference on Robotics and Automation (ICRA)*, 2019, pp. 6023–6029. DOI: [10.1109/ICRA.2019.8794127](https://doi.org/10.1109/ICRA.2019.8794127).
- [Shared autonomy] Javdani, S. *et al.* “Shared Autonomy via Hindsight Optimization.” *Robotics: Science and Systems XI (RSS)*, 2015. DOI: [10.15607/RSS.2015.XI.031](https://doi.org/10.15607/RSS.2015.XI.031).
- [Robot Data Curation] Belkhale, S. *et al.* “Robot Data Curation with Mutual Information Estimators.” *Robotics: Science and Systems XXI (RSS)*, 2025. DOI: [10.15607/RSS.2025.XXI.023](https://doi.org/10.15607/RSS.2025.XXI.023).
- [RoboMimic] Mandlekar, A. *et al.* “What Matters in Learning from Offline Human Demonstrations for Robot Manipulation.” *Conference on Robot Learning (CoRL)*, 2021; *Proceedings of Machine Learning Research*, vol. 164, 2022. 正式 proceedings：[PMLR 164](https://proceedings.mlr.press/v164/).
- [RINSE] “Learning from the Best: Smoothness-Driven Metrics for Data Quality in Imitation Learning.” 当前仅见预印本；在获得正式会议/期刊版本前，不作为投稿稿件的正式核心引用。

### D. 可扩增数据与视觉任务审计

- [MimicGen] Mandlekar, A. *et al.* “MimicGen: A Data Generation System for Scalable Robot Learning Using Human Demonstrations.” *Conference on Robot Learning (CoRL)*, 2023; *Proceedings of Machine Learning Research*, vol. 229, 2024. 正式 proceedings：[PMLR 229](https://proceedings.mlr.press/v229/).
- [DexMimicGen] Mandlekar, A. *et al.* “DexMimicGen: Automated Data Generation for Bimanual Dexterous Manipulation.” *IEEE International Conference on Robotics and Automation (ICRA)*, 2025. 从 IEEE Xplore / ICRA 2025 proceedings 导入并核对 DOI；它用于仿真数据管线，不可替代真机滤波器因果记录。
- [AHA] “AHA: A Vision-Language-Model for Detecting and Reasoning Over Failures in Robotic Manipulation.” arXiv:2410.00371, 2024. 原文：[arXiv](https://arxiv.org/abs/2410.00371)，项目页：[AHA-VLM](https://aha-vlm.github.io/)。目前未查到正式会议或期刊 DOI，应标为预印本。
- [RoboReward] “RoboReward: General-Purpose Vision-Language Reward Models for Robotics.” arXiv:2601.00675, 2026. 原文：[arXiv](https://arxiv.org/abs/2601.00675)，项目页：[RoboReward Bench](https://crfm.stanford.edu/helm/robo-reward-bench)。目前未查到正式会议或期刊 DOI，应标为预印本。

### E. 宏观数据背景（不作为方法直接比较）

- [Data Pyramid] Ye, Y. *et al.* “Data Pyramid for Embodied Manipulation: A Survey.” 2026. 当前仅有预印本，尚无正式会议/期刊出处；可用于组会背景，不应作为投稿版 related work 的正式核心引文，直到出现 archival publication。
