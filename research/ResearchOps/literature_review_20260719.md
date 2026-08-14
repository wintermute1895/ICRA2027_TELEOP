# `zotero_import_20260719_071927` 文献组复核

该名称是 Zotero collection，不是文件目录。collection ID 为 58，包含 7 个条目，其中
`Enhancing Shared Autonomy...` 有一个重复条目和一个附件条目。

## 与当前范式的关系

| 文献 | 角色 | 对当前主线的意义 | 不能直接借用的结论 |
|---|---|---|---|
| Güleçyüz et al., RA-L 2025 | 最近的共享自主仲裁 baseline | dual-confidence、延迟下 arbitration、安全过渡 | 它解决的是共享控制/置信度仲裁，不是 reference-anchored residual policy 或数据飞轮 |
| SUBTA, 2026 | 结构化装配辅助 | 场景图、阶段/行为辅助、双臂装配 | 不能把“intent estimation”当成我们精密插入主问题；当前记录为候选，发表 venue 需核验 |
| Adaptor, 2026 | 跨操作者 few-shot 辅助 | 研究跨操作者泛化、不确定性与少样本学习 | 复杂 VLM/flow matching 不是当前最小可证伪主线；当前记录为候选 |
| RINSE, 2026 | 数据质量 baseline | 直接提醒：质量筛选必须和下游成功率绑定 | 当前是 arXiv 候选，不是顶会顶刊证据；smoothness 不能单独定义成功示范 |
| SAPS, 2026 | 共享控制/VLA 远期参照 | 学习策略与人类 teleop 的动态 blending | 任务、模型规模和目标与我们的精密插入不同；当前记录为候选 |
| Jabbour et al., 2024 | 约束 blending 参照 | MPC 约束可作为安全投影/混合层的工程参照 | HAL preprint，不能代替正式顶刊 baseline |

## 当前文献范式

最稳妥的组合不是把六篇拼成一个大而全的方法，而是：

```text
Güleçyüz: shared-autonomy baseline / arbitration
RINSE: data-quality selection warning
Tilde + DAgger: corrective data aggregation reference
DexCap: multimodal teleoperation data collection reference
我们的主线: nominal reference + learned residual + hard-case corrective replay
```

其中 Tilde 和 DAgger 说明如何通过策略犯错后的人工纠偏更新数据集；Güleçyüz说明如何做
置信度仲裁。二者不应混成一个 claim。实验首先应证明 reference-conditioned residual 在精密
插入扰动下有效，再把 corrective aggregation 作为数据获取机制验证。

## 近期精读顺序

1. Güleçyüz RA-L 2025：确认其 confidence/arbitration、延迟和稳定性边界。
2. Tilde 2024：确认其 intervention/aggregation 循环和训练测试协议。
3. DexCap 2024：确认数据采集信号、标定和多模态同步设计。
4. RINSE 2026：检查质量指标是否真的改善下游任务，而不只是平滑度。
5. SUBTA / Adaptor / SAPS：只提取与装配阶段、跨操作者或策略混合直接相关的部分。
