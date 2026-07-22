# ICRA 2027 — VIST 相关文献

> 最后更新：2026-07-19（联网搜索，Claude Code 辅助）

## 项目背景

VIST — 面向低成本外骨骼遥操作的视觉引导共享控制框架。被 IROS 2026 拒稿后改进中，目标 ICRA 2027。

详见 `papers.json` 获取完整元数据（可导入 Zotero）。

## 阅读优先级

| # | 论文 | 年份 | 为什么读 | 关系 |
|---|------|------|----------|------|
| 1 | Güleçyüz et al. — Confidence-Aware Dynamic Arbitration | RA-L 2025 | **最直接竞争者** — 也做 continuous α, confidence-based arbitration, variable impedance | ⭐⭐⭐ |
| 2 | SUBTA (Liu et al.) — Bimanual Teleoperation with Learned Intention | ICRA 2026 | 意图推断 + 任务规划，回应 Reviewer 3 的 intent 批评 | ⭐⭐⭐ |
| 3 | Jabbour et al. — MPC Approach to Blending | HAL 2024 | 同用 AKF+MPC，同技术路线，需确认已发表部分 | ⭐⭐ |
| 4 | Adaptor (Liu et al.) — Few-Shot Cross-Operator Intent Learning | ICRA 2026 | 意图不确定性建模，用噪声注入——可复用方案 | ⭐⭐ |
| 5 | RINSE (Kulkarni et al.) — Smoothness-Driven Data Quality | arXiv 2026 | 平滑度指标过滤 demo 数据，和 VIST 的"数据正则化"claim 直接相关 | ⭐ |
| 6 | SAPS (Zhou et al.) — VLA Policy Steering | arXiv 2026 | Cosine similarity 动态仲裁，VLA+teleoperation blending | ⭐ |

## 已有文献（之前 19 篇）

完整文献地图见 Obsidian: `Learning/灵巧手语义遥操作-文献地图.md`

| 类别 | 论文 | 与 VIST 关系 |
|------|------|-------------|
| 共享控制 | Intent-based Shared Control (JINT 2024) | 混合策略：融合用户运动与推断意图 |
| 共享控制 | Robot Trajectron (ICRA 2024) | CVAE 预测末端轨迹，处理意图切换 |
| 共享控制 | MPC Shared Autonomy (IEEE 2024) | MPC 做共享自主 |

## 文件说明

- `papers.json` — 6 篇新论文的完整元数据（可配合 `add_to_zotero.py` 导入）
- `README.md` — 本文
- `import_to_zotero.bib` — BibTeX 格式，Zotero File → Import 直接导入
