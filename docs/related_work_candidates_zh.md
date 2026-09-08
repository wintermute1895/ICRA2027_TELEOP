# Related Work 文献候选清单

这是论文 Related Work 的检索与阅读清单，不是最终参考文献表。请先用链接打开论文并通过 Zotero 保存原始条目，核对正式 venue、DOI 和版本；确认后再加入 `paper/current/references.bib`。

## 文献组织逻辑

```text
遥操作数据采集
        -> 示教质量与数据筛选
        -> 视觉审计、进度与失败信号
        -> 动作辅助、纠正与持续采集
```

本文要强调的研究空白是：利用经过审计的历史示教，在真实遥操作过程中连续调节辅助强度，并以固定操作者时间内获得的合格示教数量作为主要结果。

## Zotero 库状态（2026-09-06）

状态说明：`[已有]` 表示已在本地 Zotero 条目或 Better BibTeX/RDF 导出中找到；`[待保存]` 表示当前候选清单中尚未找到；`[需核验]` 表示找到相近条目，但需要确认是否为同一版本、正式 venue 或 DOI。

### 已有条目

以下条目已在本地库中找到：

`GELLO`、`ALOHA`、`Mobile ALOHA`、`UMI`、`DROID`、`Open X-Embodiment`、`MimicGen`、`DexMimicGen`、`Holo-Dex`、`AnyTeleop`、`ARCap`、`Open-TeleVision`、`EgoDex`、`EgoMI`、`RINSE`、`RoboMimic`、`Shared Autonomy via Hindsight Optimization`、`Residual Reinforcement Learning for Robot Control`、`Robot Data Curation with Mutual Information Estimators`、`Robot Learning on the Job`、`Data Pyramid for Embodied Manipulation`。

### 当前未找到或尚未保存


候选表中的论文行没有直接改写状态标记，是为了避免把标题相近但版本不同的条目误标为已保存；阅读时以本节为状态索引。

## 1. 遥操作与示教数据采集

| 优先级 | 论文                                                                                                     | 链接                                                                                                  | 阅读重点                             | 与本文关系                         | 本地 Zotero |
| --- | ------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- | -------------------------------- | ----------------------------- | --------- |
| A   | GELLO: A General, Low-Cost, and Intuitive Teleoperation Framework for Robot Manipulators (2024)        | [项目页](https://wuphilipp.github.io/gello/)                                                           | 低成本关节映射遥操作、数据质量、规模、可靠性和用户实验      | 我们使用同构关节编码器范式；本文增加采集过程中的学习型滤波 | [已有]      |
| A   | Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware（ALOHA，RSS 2023）                     | [arXiv](https://arxiv.org/abs/2304.13705)                                                           | 低成本主从采集和精细双臂示教                   | 硬件与数据来源基线，不研究采集时质量闭环          | [已有]      |
| A   | Mobile ALOHA: Learning Bimanual Mobile Manipulation with Low-Cost Whole-Body Teleoperation (2024)      | [arXiv](https://arxiv.org/abs/2405.02292)                                                           | 全身遥操作和大规模真实数据采集                  | 更广泛的遥操作系统，不针对操作者命令滤波          | [已有]      |
| A   | Universal Manipulation Interface（UMI，RSS 2024）                                                         | [项目页](https://umi-gripper.github.io/) / [arXiv](https://arxiv.org/abs/2402.10329)                   | 便携式 in-the-wild 采集、相对轨迹和延迟匹配     | 未来可迁移到其他数据来源和 embodiment 的参照  | [已有]      |
| A   | DROID: A Large-Scale In-the-Wild Robot Manipulation Dataset（RSS 2024）                                  | [项目页](https://droid-dataset.github.io/) / [RSS proceedings](https://roboticsproceedings.org/rss20/) | 大规模真机采集、任务和配置多样性、元数据             | 支持数据规模与异质性背景；可与我们的数据契约比较      | [已有]      |
| B   | Holo-Dex: Teaching Dexterity with Immersive Mixed Reality (2023)                                       | [项目页](https://holo-dex.github.io/) / [arXiv](https://arxiv.org/abs/2210.06463)                      | VR 灵巧操作示教和任务多样性                  | 支持采集范式分类，接口与本文不同              | [已有]      |
| B   | AnyTeleop: A General Vision-Based Dexterous Robot Teleoperation System                                 | [arXiv](https://arxiv.org/abs/2403.07870)                                                           | 视觉重定向和灵巧手遥操作                     | 视觉重定向采集的代表性对照                 | [已有]      |
| B   | DexCap: Scalable and Portable Mocap Data Collection System for Dexterous Manipulation（RSS 2024）        | [DOI](https://doi.org/10.15607/RSS.2024.XX.043)                                                     | 便携式手部动作捕捉、跨 embodiment 转移和可选人工纠正 | 将动作捕捉与灵巧操作纠正纳入采集范式比较          | [已有]      |
| B   | ARCap: Collecting High-quality Human Demonstrations for Robot Learning with Augmented Reality Feedback | [项目页](https://stanford-tml.github.io/ARCap/) / [arXiv](https://arxiv.org/abs/2609.02455)            | 新手数据质量、AR 反馈和触觉警告                | 最接近“采集时反馈降低对操作者经验依赖”的工作       | [已有]      |
| B   | Open-TeleVision: Teleoperation with Immersive Active Visual Feedback                                   | [项目页](https://robot-tv.github.io/) / [arXiv](https://arxiv.org/abs/2407.01512)                      | 主动视觉反馈、长时程真机遥操作                  | 是采集界面反馈，不是学习型数据质量辅助           | [已有]      |
| A   | EgoDex: Learning Dexterous Manipulation from Large-Scale Egocentric Video（ICLR 2026）                   | [arXiv](https://arxiv.org/abs/2505.11709) / [代码](https://github.com/apple/ml-egodex)                | 829 小时第一视角视频、194 个桌面操作任务         | 支持第一视角数据可扩展性的背景               | [已有]      |
| B   | EgoMI: Learning Active Vision and Whole-Body Manipulation from Egocentric Human Demonstrations         | [项目页](https://egocentric-manipulation-interface.github.io/)                                         | 同步头部/手部轨迹和主动视角建模                 | 适合未来双目/VR 扩展；需核验 venue 和 DOI  | [已有]      |

## 2. 示教质量、数据筛选与数据效用

| 优先级 | 论文 | 链接 | 阅读重点 | 与本文关系 | 本地 Zotero |
|---|---|---|---|---|---|
| A | Robot Data Curation with Mutual Information Estimators（RSS 2025） | [DOI](https://doi.org/10.15607/RSS.2025.XXI.023) | 数据评分、筛选与下游策略效用 | 支持“质量不只是数量”；主要发生在采集之后 | [已有] |
| A | RINSE: Learning from the Best: Smoothness-Driven Metrics for Data Quality in Imitation Learning（2026 预印本） | [arXiv](https://arxiv.org/abs/2604.23000) | 平滑性指标及少量数据下的策略性能 | 支持平滑性作为质量维度；需核验最新发表状态 | [已有] |
| A | What Matters in Learning from Offline Human Demonstrations for Robot Manipulation（RoboMimic，CoRL 2021） | [arXiv](https://arxiv.org/abs/2108.03298) / [项目页](https://robomimic.github.io/) | 离线模仿学习中数据、任务和模型因素 | 下游效用与控制变量基线 | [已有] |
| B | MimicGen: A Data Generation System for Scalable Robot Learning Using Human Demonstrations（CoRL 2023） | [项目页](https://mimicgen.github.io/) / [arXiv](https://arxiv.org/abs/2310.17596) | 从人工示教自动生成更多轨迹 | 采集后的数据扩增，与真机实时滤波不同 | [已有] |
| B | DexMimicGen: Automated Data Generation for Bimanual Dexterous Manipulation（ICRA 2025） | [arXiv](https://arxiv.org/abs/2410.24185) | 双臂灵巧操作数据生成与重定向 | 对比仿真/重定向扩增和真实采集 | [已有] |

## 3. 视觉轨迹审计与奖励信号

| 优先级 | 论文                                                                                                       | 链接                                                                                                                 | 阅读重点                                            | 与本文关系                    | 本地 Zotero |
| --- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------- | ------------------------ | --------- |
| A   | AHA: A Vision-Language-Model for Detecting and Reasoning Over Failures in Robotic Manipulation（2024 预印本） | [arXiv](https://arxiv.org/abs/2410.00371) / [项目页](https://aha-vlm.github.io/)                                      | 失败检测、失败原因解释和轨迹上下文                               | 支持离线 VLM 失败审计，但不是动作策略    | [待保存]     |
| A   | RoboReward: General-Purpose Vision-Language Reward Models for Robotics（2026 预印本）                         | [arXiv](https://arxiv.org/abs/2601.00675) / [benchmark](https://crfm.stanford.edu/helm/robo-reward-bench)          | success、failure、near-miss、partial progress 奖励建模 | 支持视觉弱监督和审计信号；需核验正式 venue | [待保存]     |

## 4. 共享自主、残差、纠正与持续学习

| 优先级 | 论文                                                                                   | 链接                                                                                                               | 阅读重点             | 与本文关系                         | 本地 Zotero |
| --- | ------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- | ---------------- | ----------------------------- | --------- |
| A   | Residual Reinforcement Learning for Robot Control（ICRA 2019）                         | [DOI](https://doi.org/10.1109/ICRA.2019.8794127)                                                                 | 在已有控制器上学习局部残差    | 支持有界局部修正的理论先例，但目标和训练信号不同      | [已有]      |
| A   | Shared Autonomy via Hindsight Optimization（RSS 2015）                                 | [DOI](https://doi.org/10.15607/RSS.2015.XI.032)                                                                  | 人类命令与自主辅助的融合     | 支持保留人类控制权并加入辅助                | [已有]      |
| A   | DAgger（AISTATS 2011）                                                                 | [PMLR](https://proceedings.mlr.press/v15/ross11a.html)                                                           | 在策略诱导状态上查询专家     | 是训练/数据范式，不是本文的最终优化目标          | [待保存]     |
| A   | ThriftyDAgger: Budget-Aware Imitation Learning（CoRL 2021）                            | [PMLR](https://proceedings.mlr.press/v164/)                                                                      | 专家预算分配和介入效率      | 与固定操作者预算最接近的交互学习基线            | [待保存]     |
| A   | Robot Learning on the Job（RSS 2023）                                                  | [DOI](https://doi.org/10.15607/RSS.2023.XIX.005)                                                                 | 部署中的人工介入和持续改进    | 支持干预驱动的数据闭环，但主要优化部署策略         | [已有]      |
| A   | HIL-SERL: Human-in-the-Loop Reinforcement Learning for Robot Manipulation（CoRL 2024） | [项目页](https://hil-serl.github.io/) | 人工介入、恢复和强化学习 | 可用于纠正数据对比，但不是示教采集滤波 | [待保存] |

## 5. 算法基础与数学来源

以下表格用于重写 Method。正式发表出处和下载链接分列；arXiv 版本用于阅读，不能替代正式出版记录。

| 概念        | 论文准确名称                                                                                           | 正式出处                   | arXiv 或下载                                                                                                    | Method 中需要定义的内容      | 本地 Zotero |
| --------- | ------------------------------------------------------------------------------------------------ | ---------------------- | ------------------------------------------------------------------------------------------------------------ | -------------------- | --------- |
| 条件潜变量建模   | Auto-Encoding Variational Bayes                                                                  | ICLR 2014              | [arXiv:1312.6114](https://arxiv.org/abs/1312.6114)                                                           | ELBO、先验/后验、重参数化、KL 项 | [待保存]     |
| 因果序列建模    | Attention Is All You Need                                                                        | NeurIPS 2017           | [arXiv:1706.03762](https://arxiv.org/abs/1706.03762)                                                         | 缩放点积注意力和因果 mask      | [待保存]     |
| 交互式模仿学习   | A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning（DAgger） | AISTATS 2011，PMLR 15   | [PMLR](https://proceedings.mlr.press/v15/ross11a.html)                                                       | 学习器诱导状态、专家查询、分布偏移    | [需核验]     |
| 预算约束的专家介入 | ThriftyDAgger: Budget-Aware Novelty and Risk Gating for Interactive Imitation Learning           | CoRL 2021，PMLR 164     | [arXiv:2109.08273](https://arxiv.org/abs/2109.08273) / [PMLR 卷](https://proceedings.mlr.press/v164/)         | 介入预算、风险/新颖性门控        | [待保存]     |
| 残差控制      | Residual Reinforcement Learning for Robot Control                                                | ICRA 2019              | [DOI](https://doi.org/10.1109/ICRA.2019.8794127)                                                             | 在基础控制器上叠加有界修正        | [已有]      |
| 共享自主      | Shared Autonomy via Hindsight Optimization                                                       | RSS XI 2015            | [DOI](https://doi.org/10.15607/RSS.2015.XI.032)                                                              | 人类/自主动作组合与控制权分配      | [需核验]     |
| 部署期纠正     | Robot Learning on the Job: Human-in-the-Loop Autonomy and Learning During Deployment             | RSS XIX 2023；IJRR 2025 | [RSS DOI](https://doi.org/10.15607/RSS.2023.XIX.005) / [IJRR DOI](https://doi.org/10.1177/02783649241273901) | 人工介入数据与持续更新闭环        | [已有]      |
| 人机协同恢复    | HIL-SERL: Human-in-the-Loop Reinforcement Learning for Robot Manipulation                        | CoRL 2024              | [项目页](https://hil-serl.github.io/)                                                                           | 纠正介入与恢复监督            | [待保存]     |

## 6. 其他候选文献的正式出处核查

下表记录目前核验到的最强正式出处。标记为“仅预印本”表示截至
2026-09-06 尚未在本地核验到 archival venue，不把 arXiv 冒充正式发表。

| 论文 | 正式发表出处 | 下载/全文 | 状态 |
|---|---|---|---|
| GELLO | IROS 2024，DOI [10.1109/IROS58592.2024.10801581](https://doi.org/10.1109/IROS58592.2024.10801581) | [arXiv:2309.13037](https://arxiv.org/abs/2309.13037) | 已核验 |
| Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware（ALOHA） | RSS XIX 2023，DOI [10.15607/RSS.2023.XIX.016](https://doi.org/10.15607/RSS.2023.XIX.016) | [arXiv:2304.13705](https://arxiv.org/abs/2304.13705) | 已核验 |
| Universal Manipulation Interface（UMI） | RSS XX 2024，DOI [10.15607/RSS.2024.XX.045](https://doi.org/10.15607/RSS.2024.XX.045) | [arXiv:2402.10329](https://arxiv.org/abs/2402.10329) | 已核验 |
| DROID | RSS XX 2024 proceedings | [项目页](https://droid-dataset.github.io/) / [RSS proceedings](https://roboticsproceedings.org/rss20/) | proceedings 已核验，投稿前补 DOI |
| Mobile ALOHA | 本次核查未确认正式 venue | [arXiv:2405.02292](https://arxiv.org/abs/2405.02292) | 预印本/待核验 |
| Holo-Dex | 本次核查未确认正式 venue | [arXiv:2210.06463](https://arxiv.org/abs/2210.06463) / [项目页](https://holo-dex.github.io/) | 预印本/待核验 |
| AnyTeleop | 本次核查未确认正式 venue | [arXiv:2403.07870](https://arxiv.org/abs/2403.07870) | 预印本/待核验 |
| DexCap | RSS XX 2024，DOI [10.15607/RSS.2024.XX.043](https://doi.org/10.15607/RSS.2024.XX.043) | [RSS DOI](https://doi.org/10.15607/RSS.2024.XX.043) | 已核验 |
| Open-TeleVision | 本次核查未确认正式 venue | [arXiv:2407.01512](https://arxiv.org/abs/2407.01512) / [项目页](https://robot-tv.github.io/) | 预印本/待核验 |
| ARCap | 本次核查未确认正式 venue | [arXiv:2609.02455](https://arxiv.org/abs/2609.02455) / [项目页](https://stanford-tml.github.io/ARCap/) | 预印本/待核验 |
| EgoDex | ICLR 2026（需核对最终 proceedings） | [arXiv:2505.11709](https://arxiv.org/abs/2505.11709) / [代码](https://github.com/apple/ml-egodex) | venue 已报道，待核 proceedings |
| EgoMI | 本次核查未确认正式 venue | [arXiv:2511.00153](https://arxiv.org/abs/2511.00153) / [项目页](https://egocentric-manipulation-interface.github.io/) | 预印本/待核验 |
| Robot Data Curation | RSS XXI 2025，DOI [10.15607/RSS.2025.XXI.023](https://doi.org/10.15607/RSS.2025.XXI.023) | [RSS DOI](https://doi.org/10.15607/RSS.2025.XXI.023) | 已核验 |
| RINSE | 本次核查未确认正式 venue | [arXiv:2604.23000](https://arxiv.org/abs/2604.23000) | 仅预印本 |
| RoboMimic | CoRL 2021，PMLR 164 | [arXiv:2108.03298](https://arxiv.org/abs/2108.03298) / [PMLR 卷](https://proceedings.mlr.press/v164/) | 正式卷已核验 |
| MimicGen | CoRL 2023，PMLR 229 | [arXiv:2310.17596](https://arxiv.org/abs/2310.17596) / [PMLR 卷](https://proceedings.mlr.press/v229/) | 正式卷已核验 |
| DexMimicGen | ICRA 2025 venue 需从 proceedings/DOI 补核 | [arXiv:2410.24185](https://arxiv.org/abs/2410.24185) | 待核验 |
| AHA | 本次核查未确认正式 venue | [arXiv:2410.00371](https://arxiv.org/abs/2410.00371) / [项目页](https://aha-vlm.github.io/) | 仅预印本 |
| RoboReward | 本次核查未确认正式 venue | [arXiv:2601.00675](https://arxiv.org/abs/2601.00675) / [benchmark](https://crfm.stanford.edu/helm/robo-reward-bench) | 仅预印本 |
| DexUMI | 本次核查未确认正式 venue | [arXiv:2505.21864](https://arxiv.org/abs/2505.21864) | 仅预印本 |
| Data Pyramid for Embodied Manipulation | 本次核查未确认正式 venue | [arXiv:2607.24744](https://arxiv.org/abs/2607.24744) | 综述预印本 |

## 7. 推荐阅读顺序

优先保存约 20 篇：

1. GELLO、ALOHA、UMI、DROID、ARCap、EgoDex；
2. Robot Data Curation、RINSE、RoboMimic、MimicGen；
3. AHA、RoboReward、SuccessVQA，以及一篇完整轨迹 VLM 审计论文；
4. Residual RL、Shared Autonomy、DAgger、ThriftyDAgger、Robot Learning on the Job、HIL-SERL。

每篇只需先记录一条可引用原文、页码/章节、DOI 或正式链接、它支持的 claim，以及它没有解决的问题。不要把摘要改写后直接当作本文实验结论。

## 8. 文献证据卡模板

```text
论文标题：
作者 / 年份 / venue：
DOI 或正式链接：
数据来源与 embodiment：
标注或审计内容：
方法机制：
主要实验结果：
支持 claim 的原文：
页码 / 章节 / 图表：
论文没有解决的问题：
与连续视觉动作滤波器的关系：
Zotero 导入后的 BibTeX key：
```

标记为“检索”或“需核验”的条目只是候选线索，不应未经核验直接进入投稿参考文献表。
