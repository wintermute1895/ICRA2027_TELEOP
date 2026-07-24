# ICRA 2027 — VIST Teleoperation Shared Control 文献列表

> Updated: 2026-07-22 | VIST (IROS 2026 rejected) → ICRA 2027

## 项目背景

VIST — 面向低成本外骨骼遥操作的视觉引导意图驱动共享控制框架。连续意图因子 α ∈ [0,1] 动态调度自适应卡尔曼滤波器协方差，实现自由探索↔流形约束的平滑过渡。

**三个改进方向：L1** Learning α from demonstration / **L2** Learning task manifold / **L3** Learning + Optimal Control

## 阅读优先级

| # | Paper | Priority | Why |
|---|-------|----------|-----|
| 1 | Güleçyüz et al. (RA-L 2025) | ⭐⭐⭐ | Closest competitor — also uses continuous α |
| 2 | SUBTA (ICRA 2026) | ⭐⭐⭐ | Learned intention from human pose |
| 3 | Jabbour (HAL 2024) | ⭐⭐ | Same AKF + blending architecture |
| 4 | RINSE (arXiv 2026) | ⭐⭐ | Data quality filtering |
| 5 | Adaptor (ICRA 2026) | ⭐ | Few-shot cross-operator intent learning |
| 6 | SAPS (arXiv 2026) | ⭐ | VLA + teleoperation blending |

---

## 1. Güleçyüz et al. (RA-L 2025) — Confidence-Aware Dynamic Arbitration ⭐⭐⭐

**BibTeX:**
```
@article{gulecyuz2025enhancing,
  title = {Enhancing Shared Autonomy in Teleoperation under Network Delay: 
           Transparency- and Confidence-Aware Arbitration},
  author = {Güleçyüz, Başak and Balachandran, Ribin and Panzirsch, Michael and 
            Singh, Harsimran and Hulin, Thomas and Xu, Xiao and Steinbach, Eckehard},
  journal = {IEEE Robotics and Automation Letters},
  volume = {10}, number = {10}, pages = {9654--9661}, year = {2025},
  doi = {10.1109/LRA.2025.3596436},
}
```

**最直接竞争者。** 连续 α 做共享控制动态仲裁，α 来自 principled 双置信度：
- Autonomy confidence: TP-HSMM 状态协方差（模型不确定性）
- Human confidence: 遥操作透明度（passivity controller conservatism）

**我们的差异空间:** 外骨骼无反馈下用视觉做 confidence signal；视觉在闭环内做 real-time intent estimation

**团队:** TUM + DLR, CeTI Cluster of Excellence

---

## 2. SUBTA (ICRA 2026) — Bimanual Teleop with Learned Intention ⭐⭐⭐

**BibTeX:**
```
@inproceedings{liu2026subta,
  title = {SUBTA: A Framework for Supported User-Guided Bimanual Teleoperation 
           in Structured Assembly},
  author = {Liu, Xiao and Baskaran, Prakash and Li, Songpo and Manschitz, Simon and 
            Ma, Wei and Ruiken, Dirk and Iba, Soshi},
  booktitle = {IEEE ICRA}, year = {2026},
  note = {arXiv:2603.10459},
}
```

回应 Reviewer 3 批评（"已知目标位姿"→"推断意图"）。GNN + self-attention 从人手姿态预测 task label；scene graph (graph edit distance) 规划目标位姿；9 种 gated motion behaviors。**Honda Research Institute，12人用户研究。**

**团队:** Honda Research Institute, USA

---

## 3. Jabbour et al. (HAL 2024) — MPC Blending in Shared Control ⭐⭐

**BibTeX:**
```
@article{jabbour2024mpc,
  title = {A Model Predictive Control Approach to Blending in Shared Control},
  author = {Jabbour, Elio and Vulliez, Margot and Preault, Celestin and Padois, Vincent},
  journal = {HAL preprint}, year = {2024},
  note = {hal-04753213. INRIA Aucius team},
}
```

同一技术路线（AKF + blending）。AKF 补偿局部误差 + Procrustes 校正全局偏差 + MPC 约束最优 blending。需确认哪些已发表→未发表的方向才是空间。

**团队:** INRIA Bordeaux (Aucius), CESI Lineact, France

---

## 4. RINSE (arXiv 2026) — Data Quality for IL ⭐⭐

**BibTeX:**
```
@article{kulkarni2026rinse,
  title = {RINSE: Learning from the Best: Smoothness-Driven Metrics for Data Quality 
           in Imitation Learning},
  author = {Kulkarni, Soham and Dhar, Raayan and Cui, Yuchen},
  journal = {arXiv:2604.23000}, year = {2026},
  note = {UCLA},
}
```

直接相关 VIST "物理级数据正则化" claim。SAL (频域) + TED (空间域) 过滤低质量 demo。用 1/6 数据 +16% 成功率。

**团队:** UCLA

---

## 5. Adaptor (ICRA 2026) — Few-Shot Cross-Operator Intent ⭐

**BibTeX:**
```
@inproceedings{liu2026adaptor,
  title = {Adaptor: Advancing Assistive Teleoperation with Few-Shot Learning 
           and Cross-Operator Generalization},
  author = {Liu, Yu and Yin, Yihang and Huang, Tianlv and Yan, Fei and Xu, Yuan and 
            Hong, Weinan and Han, Wei and Cao, Yue and Chen, Xiangyu and Fan, Zipei and Song, Xuan},
  booktitle = {IEEE ICRA}, year = {2026},
  note = {arXiv:2604.09462},
}
```

两阶段：噪声注入建模 uncertainty + VLM + Conditional Flow Matching few-shot。+41.9% 成功率。

---

## 6. SAPS (arXiv 2026) — VLA + Teleoperation Blending ⭐

**BibTeX:**
```
@article{zhou2026saps,
  title = {SAPS: Shared Autonomy for Policy Steering by Blending Teleoperation 
           with a Pretrained VLA},
  author = {Zhou, Crystal and Yang, Jehan and Weber, Douglas J. and Erickson, Zackory},
  journal = {arXiv:2606.15568}, year = {2026},
  note = {CMU},
}
```

余弦相似度动态仲裁。π0.5 从 15%→92.6%。和低成本硬件路线不完全一致。

**团队:** CMU

---

## 竞争格局总结

| 维度 | VIST (Ours) | Güleçyüz (2025) | SUBTA (2026) | 我们的机会 |
|------|-------------|-----------------|--------------|-----------|
| α 来源 | Heuristic | TP-HSMM principled | GNN intent | **Learning α + vision in loop** |
| 目标几何 | 人工标定 | Task demos | Scene graph | **Few-shot manifold (NeRF/3DGS)** |
| 硬件 | 低成本外骨骼 | Haptic force-fb | VR + force | **Vision-as-feedback** |
| 理论 | 无 | 3-port passivity | User study stats | **LQG/MPC analysis** |

## 相关工具

- `add_to_zotero.py` — 半自动 Zotero 导入脚本（支持 BibTeX 和 direct 两种模式）
- `papers_metadata.json` — 机器可读的论文元数据
