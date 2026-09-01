## Abstract
当前，数据的数量和质量已经成为了具身智能领域发展的瓶颈之一，虽然通用机器人大模型完成pick and place 等简单任务已经不算难题，但通过少量的遥操示教数据让机器人完成如USB插接、RJ45网线插接等精细动作依然受到高质量数据瓶颈制约；如何快速、低成本地让新手也能采集高质量的机器人真机数据是当下关注的话题之一。我们的工作抽象出了一类具有相同特征的精密插接任务，并提出了一种以VAE Transformer 残差学习
为核心的learning based filter，能够针对这一类任务从示教数据的轨迹、传感器中学习到“好”且自然、符合人类动作直觉的数据的特征与概率分布，并在数据采集的过程中对遥操数据进行修正使采集的数据整体更加接近“好分布”，在采集过程中使采集的速度和质量逐渐提高，让新手也更容易采集到专家示教数据，从而提高这一类task的数据质量，降低采集成本，使下游模型的任务成功率更高。

## 1.Introduction
目前，具身智能领域的发展已经受到了数据瓶颈的制约，在Yifan Ye等人的关于数据金字塔的综述里提出了很多关于数据质量的问题；首先，真机数据在UMI Ego 仿真数据等等新数据采集范式的影响下依然维持着重要的地位，也依然数量最少且难以采集；并且，目前对数据质量的评估和审计也没有跟上数据采集需求的增长速度，因此，在缺乏高质量数据规范、审计标准和契约的基础上，已有的很多真机数据也是缺失标签且没有泛化价值的，而目前，不管是VLA模型还是如ACT Diffusion Policy等以BC为基础的模型完成如pick and place等对动作的精密程度、对力反馈的需求程度都不够高的任务已经能够达到较高且稳定的成功率，但需要精细操作的任务例如用五指灵巧手和七自由度机械臂完成例如USB插接、RJ45网线插接等任务依然存在数据瓶颈，因此我们提出了一种方法：这种方法使用采集到的数据，将人工筛选过的第一批数据送入A，并且用数据审计的指标去训练一个能够约束并影响GELLO范式下的同构关节编码器数据采集过程的filter模型，使用VAE和Attenntion机制从高维数据中自动提取出真正影响这类任务成功率和数据质量的几个低维流形的数据，并用filter更快、更好地采集数据的过程不断强化自身，形成一个特定类型任务下的数据飞轮。我们的核心贡献：
1.对一类问题进行抽象，并且用非手工特征工程的方式找到了审计这类数据质量的方法并根据下游模型的成功率提高验证了其有效性。
2.提出了一个learing based的VAE  Transformer fitler，与残差学习的思想结合，并用对于机器人数据的客观质量指标和任务成功率、采集效率同时提高的结果验证了这类filter的有效性。
3.实现部署了特定类型任务下的真机数据采集的数据飞轮。

## 2.Related Work

### 遥操作示教与共享自主采集

低成本遥操作接口是扩展真实机器人示教数据的重要基础。GELLO 以同构关节编码器提供直观的关节空间遥操作；UMI 将手持末端的相对运动记录为可重定向的操作轨迹；Mobile ALOHA、DROID 等工作则通过低成本全身遥操作或跨场景采集扩大真实机器人数据规模。这些系统主要回答如何获得更多示教以及如何降低操作者的控制门槛。与之不同，本文不提出新的遥操作硬件或完整自主策略，而是在既有遥操作链路中加入学习型命令辅助，研究其是否能提高视觉可观测精密操作任务中单位操作者时间获得有效示教的数量。

### 示教数据质量、数据筛选与数据契约

示教质量会影响模仿学习策略的效用，但质量定义通常依赖任务和下游用途。Robot Data Curation with Mutual Information Estimators 以状态—动作互信息贡献刻画轨迹的多样性和可预测性，并用下游策略性能验证筛选效果；RINSE 等工作则从平滑性等轨迹性质出发评估示教。此类方法主要在采集后对已有数据排序或过滤，不能直接构成跨任务的通用质量真值。本文不提出普适的数据质量标量，而是为视觉可观测精密操作定义可审计的数据契约：显式记录图像、命令、执行状态、时间同步、任务阶段、终止事件和操作者事件，并以透明逻辑门区分用于动作学习的 A_action 与用于失败和异常分析的 A_audit。

### VLM 视觉审计与轨迹表征

近期工作开始使用视觉语言模型对机器人轨迹进行成功判定、失败诊断、进度评估和奖励建模。SuccessVQA 类方法将视觉问答用于任务成功识别；AHA 训练 VLM 检测操作失败并解释失败原因；RoboReward 则使用真实机器人轨迹以及 failure、near-miss 和 partial-progress 样本训练通用视觉语言奖励模型。这些工作说明视觉模型可以为轨迹提供任务相关的弱监督信号，但其输出仍受视角、任务分布和提示词影响，不能直接视为动作纠正真值。本文将冻结的视觉编码器或 VLM 审计器作为 filter 的视觉输入与离线标注工具：视觉模型提供任务阶段、可见性、停滞、回退和进度一致性等带置信度的信号；动作修正目标仍由时间同步的遥操作轨迹和后续有效动作构造。

### 学习型共享控制、残差策略与动作滤波

共享自主、残差策略学习和 learning-from-corrections 工作表明，学习模块可以在保留人类控制权的前提下辅助或修正执行动作。Residual Policy Learning 将学习策略作为已有控制器上的残差，以降低从零学习完整控制器的难度；学习型共享控制则结合人类输入、机器人状态和环境观测进行在线辅助。这些方法通常以自主任务成功、意图推断或策略性能为主要目标。本文将学习模块限制为因果、视觉条件化且经过安全投影的命令滤波器：它不预测操作者意图，不输出无约束自主动作，也不把规划轨迹直接作为动作教师，而是从审计通过的示教中学习任务阶段相关的局部动作修正。

### 交互式模仿学习与部署中的持续数据采集

DAgger 及其后续工作通过在策略诱导状态上查询专家来缓解行为克隆的分布偏移；ThriftyDAgger、Robot Learning on the Job 和 intervention-based learning 进一步关注有限专家时间下的人工介入、风险控制和部署中持续改进。这些工作表明采集、学习和再采集可以形成闭环，但通常以最终策略成功率、专家查询次数或人工介入成本为主要结局。本文关注不同且互补的结局：在固定操作者主动时间、reset 数、场景配置配额和安全边界下，视觉审计驱动的滤波器能否使下一轮采集获得更多 A_action episode。下游 ACT/DP 成功率只作为独立的数据效用验证，不参与 A_action 的准入。

### 视觉可观测的精密对齐与操作任务

本文不以 contact-rich assembly、力控或接触状态估计为研究对象，也不重新定义某一种具体插接任务。我们关注的是一类视觉可观测、目标单一、动作公差有限且需要局部精细对齐和连续轨迹控制的操作任务。任务可以包含对准、短行程操作或其他可由图像和机器人状态审计的精细动作，但不要求系统估计连续力/力矩、内部接触状态或柔性物体动力学。该边界使研究重点保持在轨迹质量、任务阶段识别、视觉审计和人机协同采集效率，而不是把抓取、力反馈、未知遮挡和全局规划混入同一主张。


## 3.Method
###  3.1 Task Formulation and Auditable Data Protocol
我们从这一类任务中抽象出其特征和边界 并根据一些理由做了其人工数据审计的结构化定义
以及对于这类任务 到底什么才是好的数据
###  3.2 Vision-Language-Conditioned Residual Filter
我们的filter模型的输入输出是什么 有几层结构 VLM模型在这中间的作用是什么

### 3.3 Corrective Supervision and Offline Training

### 3.4 Safe Iterative Data Collection


## 4.Experienment
我们的实验为了回答以下哪几个问题，我们做了什么样的设置，采用了什么样的硬件和软件 ，做了哪些消融

## 5.Limitation and Conclusion


## References


## Formal Reference Candidates (to import into Zotero)

> 使用说明：以下条目是正文五个 Related Work 小节所需的正式出处。优先从 DOI 或 proceedings 页面导入 Zotero，而不是从 arXiv 导入。RSS、PMLR/CoRL 的部分论文有正式 proceedings 但没有传统期刊 DOI；这种情况保留正式 proceedings URL，不伪造 DOI。Data Pyramid 和 RINSE 目前仅为预印本，不应在投稿稿件中作为“正式发表论文”引用。

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
