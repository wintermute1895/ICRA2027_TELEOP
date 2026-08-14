# ResearchOps

这是 VIST 精密装配研究的证据和实验工作台，不替代 Zotero，也不自动改写 Zotero
数据库。它把研究推进约束成一条可审计链路：

```text
研究边界 -> 可证伪 claim -> 文献原始证据 -> 可执行实验 -> episode/evaluation artifact
```

## 目录

- `research_goal.md`：当前唯一有效的研究边界与主问题。
- `claims.json`：每个候选贡献的精确定义、最近工作、反例和验收实验。
- `experiments.json`：A/B 条件、数据需求、指标、代码接口与停止条件。
- `papers/`：已核实论文的逐篇证据卡，以及网络搜索候选；候选不等于可引用证据。
- `reports/`：由工具生成的本地审计、矩阵和周报，默认不提交。
- `tools/`：只读审计、schema 检查、矩阵生成和网络候选检索。

## 日常工作流

1. 写/更新 `research_goal.md`，先收紧问题边界。
2. 在 `claims.json` 新增 claim 前必须填入 `counterexample`、`required_evidence` 和
   `experiment_ids`。没有反例和实验的想法只能是备忘，不是论文主张。
3. 用本地导出的 Better BibTeX JSON 做审计：

```bash
python3 Vault/ResearchOps/tools/research_ops.py audit-zotero \
  --input 'Zotero/better-bibtex/My Library-VIST*.json' \
  --output Vault/ResearchOps/reports/zotero_audit.json
```

4. 先做外部候选搜索，再逐篇打开原文/官方页面核验 DOI、会期、实验和限制：

```bash
python3 Vault/ResearchOps/tools/search_openalex.py \
  --query 'robotic precision insertion teleoperation demonstration learning' \
  --from-year 2023 --output Vault/ResearchOps/papers/candidates/openalex_insertion.json
```

一轮完整的近三年扫描使用已版本化的查询集，并按日期隔离候选：

```bash
python3 Vault/ResearchOps/scripts/run_recent_scan.py
```

5. 只有核验后才把论文写成 `papers/<citekey>.md`，并把其 ID 加入 `claims.json`。
6. 每次准备实验前运行：

```bash
python3 Vault/ResearchOps/tools/research_ops.py validate
python3 Vault/ResearchOps/tools/research_ops.py check-code-paths
python3 Vault/ResearchOps/tools/research_ops.py matrix \
  --output Vault/ResearchOps/reports/claim_evidence_matrix.md
python3 Vault/ResearchOps/tools/research_ops.py brief \
  --output Vault/ResearchOps/reports/research_brief.md
```

## 与代码的边界

`/mnt/F/ICRA2027_TELEOP` 是实时遥操、同步、录制与 episode 基础设施。ResearchOps
只链接它的只读导出/评分入口，不控制机器人。

`/mnt/F/DexCatch-cx-integretion` 只作为离线轨迹、可达性、安全和名义参考评估能力；
不进入遥操实时闭环，也不改变 DexCatch 的项目叙事。

## 近期检索纪律

“近三年”按 2023--2026 过滤。候选优先核验 ICRA、IROS、RSS、CoRL、RA-L、T-RO、IJRR、
Science Robotics、Nature Machine Intelligence，以及确实以机器人为主的 NeurIPS/ICLR/ICML。
arXiv 只作候选线索，不能作为“顶会顶刊证据”。
