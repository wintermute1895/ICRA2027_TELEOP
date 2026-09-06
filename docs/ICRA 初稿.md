## Abstract
当前，数据的数量和质量已经成为了具身智能领域发展的瓶颈之一，虽然通用机器人大模型完成pick and place 等简单任务已经不算难题，但通过少量的遥操示教数据让机器人完成如USB插接、RJ45网线插接等精细动作依然受到高质量数据瓶颈制约；如何快速、低成本地让新手也能采集高质量的机器人真机数据是当下关注的话题之一。我们的工作抽象出了一类具有相同特征的任务，并提出了一种以VAE Transformer 残差学习
为核心的learning based filter，能够针对这一类任务从示教数据的轨迹、传感器中学习到“好”且自然、符合人类动作直觉的数据的特征与概率分布，并在数据采集的过程中对遥操数据进行修正使采集的数据整体更加接近“好分布”，在采集过程中使采集的速度和质量逐渐提高，让新手也更容易采集到专家示教数据，从而提高这一类task的数据质量，降低采集成本，使下游模型的任务成功率更高。

## 1.Introduction
目前，具身智能领域的发展已经受到了数据瓶颈的制约，在Yifan Ye等人的关于数据金字塔的综述里提出了很多关于数据质量的问题；首先，真机数据在UMI Ego 仿真数据等等新数据采集范式的影响下依然维持着重要的地位，也依然数量最少且难以采集；并且，目前对数据质量的评估和审计也没有跟上数据采集需求的增长速度，因此，在缺乏高质量数据规范、审计标准和契约的基础上，已有的很多真机数据也是缺失标签且没有泛化价值的，而目前，不管是VLA模型还是如ACT Diffusion Policy等以BC为基础的模型完成如pick and place等对动作的精密程度、对力反馈的需求程度都不够高的任务已经能够达到较高且稳定的成功率，但需要精细操作的任务例如用五指灵巧手和七自由度机械臂完成例如USB插接、RJ45网线插接等任务依然存在数据瓶颈，因此我们提出了一种方法：这种方法使用采集到的数据，将人工筛选过的第一批数据送入A，并且用数据审计的指标去训练一个能够约束并影响GELLO范式下的同构关节编码器数据采集过程的filter模型，使用CVAE和Attenntion机制从高维数据中自动提取出真正影响这类任务成功率和数据质量的几个低维流形的数据，并用filter更快、更好地采集数据的过程不断强化自身，形成一个特定类型任务下的数据飞轮。我们的核心贡献：
1.对一类问题进行抽象，并且用非手工特征工程的方式找到了审计这类数据质量的方法并根据下游模型的成功率提高验证了其有效性。
2.提出了一个learing based的CVAE  Transformer fitler，与残差学习的思想结合，并用对于机器人数据的客观质量指标和任务成功率、采集效率同时提高的结果验证了这类filter的有效性。
3.实现部署了特定类型任务下的真机数据采集的数据飞轮。

## 2.Related Work

### 2.1 遥操作示教与共享自主采集

  2026年的综述data pyrmid里提出了具身智能数据的几种形式（真机，仿真，UMI ，Ego）如果按照数据来源与数据类型对数采设备/系统/范式进行分类的话，可以分成以GELLO为代表的3D打印关节编码器类，以ALOHA为代表的主从同构直接映射采集类，以VR headset为数采设备的holo dex类，以视觉重定向和IK采集臂—手灵巧操作的anyteleop类，Ego数据有待找一篇代表性工作，其中，我们的data flywheel使用的是以GELLO为范式的数采系统，但在未来我们也将用这种方法集成到以双目视觉或VR headset+ik采集的仿真和真机数据中。而共享自主方面的工作中，某某工作有效地证明了xx共享控制方法在xx数采系统上能够提高机器人数据采集的效率和质量，而我们受到了xx工作的启发，并且和xx不同的是，我们将shared control融合进数据采集系统并且使shared control自主进化，并且规避了手工特征工程。

### 2.2 机器人示教数据质量、数据筛选与视觉审计

数据的审计和评估是产生高质量数据的重要途径之一，Robot data curation等几项工作明确指出了离线数据质量审计可以提升下游模型的表现，而想要提高数据审计的质量和速度，VLM模型辅助审计是一个当下的热点话题，SuccessVQA、AHA、RoboReward 等工作使用视觉模型判断成功、失败、阶段、进度或奖励。但现有方法大多是“采集后评价”或“输出 reward/label”，没有把视觉审计信号进一步用于实时动作辅助，并改善下一轮数据采集。

### 2.3学习型共享控制、残差策略与动作纠正

 自从遥操作开始成为机器人数据采集的重要范式之一，通过人机交互进行共享控制也成为了辅助数据采集的重要方向，Residual Reinforcement Learning for Robot Control、 Residual Policy Learning、HIL-SERL、learning-from-corrections、shared autonomy、FlowCorrect 等工作提出了通过离线审计数据的残差来训练出更好的策略或更好的数据驱动共享控制模型，而我们的目标是不仅把共享控制作为一个辅助数据采集的策略而是作为数据采集闭环中的一部分，用控制策略采集好的数据的同时，好的数据也再在驱动控制策略的进化

### 2.4 交互式模仿学习与持续数据采集闭环

失败恢复数据是让机器人模型能够真正学到规律和任务的corner cases的宝贵数据，xx工作研究了什么时候需要纠正，xx工作研究了在xx类型任务的哪些时间段需要产生纠正，而xx和xx为代表的一类工作分别研究了人类在数据采集时的动作纠正数据是如何把进入模型，需要优化什么，怎么评估效果，而我们的目的不是用纠偏数据训练更好的模型，而是将纠偏数据用于数采辅助的过程中，不断用高质量数据使纠偏filter模型能够学习到专家示教的纠正规律从而从数据源头使单位时间内采集的有效数据更多

## 3.Method
###  3.1 Task Formulation and Auditable Data Protocol
我们的任务边界是：需要较为精密的对齐（容差xxmm~xxmm之间）、可能需要操作员反复尝试动作、不需要较为复杂的接触力的任务；我们将所有我们研究的任务分为以下几个阶段：a接近 b对齐 c短程 插入或轻接触/触碰；以下几类任务不在我们研究的范围之内：xxx\xxxx\xxx；在本文中，我们从简单到难设计了以下几类实验：1.圆孔对齐 2.按按键3.插充电器4.usb 5.笔记本网线；我们的数据协议和数据分类是……（怎么感觉这部分需要分出来一部分写进实验里）；并且需要在这里的结束位置介绍一下我们的整个模型架构和数据流转过程
###  3.2 Vision-Language-Conditioned Residual Filter
我们的filter模型的输入输出是什么 有几层结构 VLM模型在这中间的作用是什么；而我们记录residual时 采集数据标注出residual是不现实的，所以我们只标注操作员在发现没有对齐时的纠正动作的开始和结束的阶段，一个典型的过程包括接近——对齐——修正开始——修正结束——对齐——完成任务。而VLM在经过滑动窗口和attention之后能够理解任务全局的内容和阶段并且能够自动标注和提高标注能力
### 3.3 Corrective Supervision and Offline Training
我们构造出residual之后，让进入“好数据”的filter 训练flywheel跑起来，同时，为了防止模型自我强化，我们做了xx的操作；并且为了防止模型提前看到未来，我们做了mask
### 3.4 Safe Iterative Data Collection
residual模型训练好之后，我们在实际部署时不依赖模型的VLM语义标注和审计，我们使用SigSLP2进行embedding的同时让filter模型给出控制时的纠正动作，为了能有效地评估模型能力，我们使用如下方式进行evaluation……

## 4.Experienment
我们的实验为了回答以下哪几个问题，我们做了什么样的设置，采用了什么样的硬件和软件 ，做了哪些消融：

我们的实验回答以下几个问题：（这些问题我觉得是核心的研究内容，应该再从中提取抽象出核心的点提出intro里目前研究缺少的内容和我们的三个contribution）
1.对于动作分布残差的记录标注和学习是否能真正然模型学习到何时应该对人类遥操作施加辅助，应该施加多大的辅助才能采集到更好的数据
2.对于这类任务的抽象是否合理，是否有推广意义
3.我们的data flywheel如何能防止自我强化，如何合理评估模型的推理能力
4.VLM在这样的数据下是否能有效地自我进化提高对数据的标注能力
5.data flywheel是否能真正意义上提高合格数据的采集效率，并且提高下游模型的能力
6.学习残差/纠正动作和一次性成功的流畅动作两种专家数据，并且收集一些失败样本是否能让模型真正理解失败恢复应该怎么做

我们的实验内容设置如下：
### 4.1 Setup and Data Protocol
我们采用的硬件为7自由度人型机器人机械臂和同构的遥操臂以及6自由度灵巧手，算力平台为4090显卡训练ACT策略，5070笔记本训练和评测filter模型并且承担filter模型的实时推理部署；我们的数据协议和处理流程为……数据的结构是……我们的任务实验环境和场景、物体泛化如下设置为……我们的任务有以下几个：……我们抽象的任务本质结构、阶段分层和成功的定义为……我们的模型冷启动阶段的数据采集和训练方式为……
### 4.2 Correction-Aware Action Assistance
我们对照了原始轨迹、时序滤波、learing based filter的效果，比较了任务成功率、轨迹平滑度、数据质量综合评分、数据采集效率、新手/专家采集效率差距等等指标，证明1.对于像“专家一次成功”的数据，filter的干预很少并且做了合适的时序平滑 2.对于新手“反复尝试”的轨迹，filter模型能够在恰当的时机施加合适的干预让轨迹更加平滑稳定减少抖动和反复尝试。
消融实验：

### 4.3 VLM Audit and Cross-Round Validation
这部分不太会设计实验和消融啊

### 4.4 Data-Collection Efficiency and Downstream Utility
主要看模型部署
消融实验：



## 5.Limitation and Conclusion
我们的数据采集平台还有以下几个缺陷：模型冷启动阶段对人工标注的依赖较高，高质量的初始50条数据可以很大程度上影响模型之后的能力、我们的模型目前只部署在关节编码器based采集环境，但是其实我们的这种方式最适合的是VR或者retargeting遥操滤波控制，但由于我们年的硬件设备平台不适合部署这样的环境，并且IK算法的调试没有达到我们理想的目标所以没有尝试部署，但后续我们会尝试在仿真里部署，通过模型来强化仿真遥操数采的能力。另外，我们的算法高度依靠针对任务进行设定和适配，虽然做了跨任务泛化实验，但也没法证明我们的方法可以继续外推，但我们认为这是一个有潜力的方向。此外，我们对VLM的潜力发挥并不算非常充分，我们也没有进行VLA模型的部署和对比，对于ACT而言的“好数据”不一定等于VLA模型和以后新的架构的模型的好数据。但我们做到了以下几点的验证：……

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
