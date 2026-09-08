# Related Work Candidate Map

This is a reading and citation-retrieval list for the ICRA draft. It is not the
paper bibliography yet. Save the primary paper in Zotero, verify the final
venue/DOI, and record one exact supporting passage before moving an item into
`paper/current/references.bib`.

The target narrative has four links:

```text
teleoperation data collection
        -> demonstration quality and curation
        -> visual auditing / progress / failure signals
        -> assistance, correction, and iterative collection
```

Our central gap is data collection itself: using audited historical
demonstrations to continuously modulate assistance during real teleoperation,
with valid demonstrations per operator-minute as a primary outcome.

## Zotero Inventory (2026-09-06)

Status legend: `[已有]` means a matching item was found in the local Zotero
Better BibTeX/RDF exports; `[待保存]` means no clear local match was found;
`[需核验]` means a similar item exists but the exact version, venue, or DOI
still needs checking.

### Already in the local library

`GELLO`, `ALOHA`, `Mobile ALOHA`, `UMI`, `DROID`, `Open X-Embodiment`,
`MimicGen`, `DexMimicGen`, `Holo-Dex`, `AnyTeleop`, `ARCap`, `Open-TeleVision`,
`EgoDex`, `EgoMI`, `RINSE`, `RoboMimic`, `Shared Autonomy via Hindsight
Optimization`, `Residual Reinforcement Learning for Robot Control`, `Robot Data
Curation with Mutual Information Estimators`, `Robot Learning on the Job`, and
`Data Pyramid for Embodied Manipulation`.

### Not found or not yet saved

and the broad search candidates in Section 2 were not found as unambiguous
matches in the local Zotero exports. Save these through Zotero Connector and
verify the final bibliographic version.

The tables retain their original rows and links so that a near-title match is
not silently treated as the same paper. Use this inventory as the status index.

## 1. Teleoperation And Demonstration Collection

| Priority | Work | Link | What to extract | Relation to our work | Local Zotero |
|---|---|---|---|---|---|
| A | GELLO: A General, Low-Cost, and Intuitive Teleoperation Framework for Robot Manipulators (2024) | [project](https://wuphilipp.github.io/gello/) | Quality, scale, reliability, and operator study for low-cost joint-mapped teleoperation | Our capture interface is in the same kinematic-twin family; we add learned filtering during collection | [Present] |
| A | Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware (ALOHA, RSS 2023) | [arXiv](https://arxiv.org/abs/2304.13705) | Low-cost master-slave collection and fine-grained bimanual demonstrations | Demonstration hardware/data source baseline, not a collection-time quality loop | [Present] |
| A | Mobile ALOHA: Learning Bimanual Mobile Manipulation with Low-Cost Whole-Body Teleoperation (2024) | [arXiv](https://arxiv.org/abs/2405.02292) | Whole-body teleoperation and scaling real demonstrations | Broader teleoperation setting; does not target adaptive filtering of operator commands | [Present] |
| A | Universal Manipulation Interface (UMI, RSS 2024) | [project](https://umi-gripper.github.io/) / [arXiv](https://arxiv.org/abs/2402.10329) | Portable in-the-wild data collection, relative trajectory representation, latency matching | Alternative data source; useful for discussing future embodiment portability | [Present] |
| A | DROID: A Large-Scale In-the-Wild Robot Manipulation Dataset (RSS 2024) | [project](https://droid-dataset.github.io/) / [RSS proceedings](https://roboticsproceedings.org/rss20/) | Large-scale real-robot collection, task/configuration diversity, metadata | Evidence for scale and heterogeneity; compare its recording contract with ours | [Present] |
| B | Holo-Dex: Teaching Dexterity with Immersive Mixed Reality (2023) | [project](https://holo-dex.github.io/) / [arXiv](https://arxiv.org/abs/2210.06463) | VR-based dexterous demonstration collection and task diversity | Different interface; supports the collection-paradigm taxonomy | [Present] |
| B | AnyTeleop: A General Vision-Based Dexterous Robot Teleoperation System | [arXiv](https://arxiv.org/abs/2403.07870) | Vision-based retargeting and dexterous teleoperation | Relevant alternative to joint-mapped capture | [Present] |
| B | DexCap: Scalable and Portable Mocap Data Collection System for Dexterous Manipulation (RSS 2024) | [DOI](https://doi.org/10.15607/RSS.2024.XX.043) | Portable hand motion capture, embodiment transfer, and optional human correction | Extends the collection-paradigm comparison toward mocap and dexterous correction | [Present] |
| B | ARCap: Collecting High-quality Human Demonstrations for Robot Learning with Augmented Reality Feedback | [project](https://stanford-tml.github.io/ARCap/) / [arXiv](https://arxiv.org/abs/2609.02455) | Novice data quality, visual feedback, and haptic warnings during collection | Closest evidence that collection-time feedback can reduce operator expertise dependence | [Present] |
| B | Open-TeleVision: Teleoperation with Immersive Active Visual Feedback | [project](https://robot-tv.github.io/) / [arXiv](https://arxiv.org/abs/2407.01512) | Active visual feedback and long-horizon real-robot teleoperation | Collection interface feedback, but not learned data-quality assistance | [Present] |
| B | EgoDex: Learning Dexterous Manipulation from Large-Scale Egocentric Video (ICLR 2026) | [arXiv](https://arxiv.org/abs/2505.11709) / [project](https://github.com/apple/ml-egodex) | 829 hours of egocentric video and 194 tabletop tasks | Evidence for first-person data as a scalable source, not synchronous robot teleoperation | [Present] |
| C | EgoMI: Learning Active Vision and Whole-Body Manipulation from Egocentric Human Demonstrations | [project](https://egocentric-manipulation-interface.github.io/) / [arXiv](https://arxiv.org/abs/2511.00153) | Synchronized head/hand trajectories and active-viewpoint modeling | Useful for future multi-camera/VR extension; verify venue and DOI | [Present] |

## 2. Demonstration Quality, Curation, And Data Utility

| Priority | Work | Link | What to extract | Relation to our work | Local Zotero |
|---|---|---|---|---|---|
| A | Robot Data Curation with Mutual Information Estimators (RSS 2025) | [DOI](https://doi.org/10.15607/RSS.2025.XXI.023) | Data scoring/selection and downstream policy utility | Supports quality-over-count motivation; operates mainly after collection | [Present] |
| A | RINSE: Learning from the Best: Smoothness-Driven Metrics for Data Quality in Imitation Learning (2026 preprint) | [arXiv](https://arxiv.org/abs/2604.23000) | Smoothness metrics and reduced-data policy performance | Supports smoothness as a measurable quality dimension; verify current publication status | [Present] |
| A | What Matters in Learning from Offline Human Demonstrations for Robot Manipulation (RoboMimic, CoRL 2021) | [arXiv](https://arxiv.org/abs/2108.03298) / [project](https://robomimic.github.io/) | Dataset/task/model factors affecting offline imitation | Baseline for downstream utility and controlled data comparisons | [Present] |
| B | MimicGen: A Data Generation System for Scalable Robot Learning Using Human Demonstrations (CoRL 2023) | [project](https://mimicgen.github.io/) / [arXiv](https://arxiv.org/abs/2310.17596) | Automated trajectory generation and data scaling | Data expansion after demonstrations, distinct from real-time collection filtering | [Present] |
| B | DexMimicGen: Automated Data Generation for Bimanual Dexterous Manipulation (ICRA 2025) | [arXiv](https://arxiv.org/abs/2410.24185) | Dexterous/bimanual data generation and retargeting | Useful boundary: synthetic/retargeted augmentation versus real capture | [Present] |

## 3. Visual Trajectory Auditing And Reward Signals

| Priority | Work | Link | What to extract | Relation to our work | Local Zotero |
|---|---|---|---|---|---|
| A | AHA: A Vision-Language-Model for Detecting and Reasoning Over Failures in Robotic Manipulation (2024 preprint) | [arXiv](https://arxiv.org/abs/2410.00371) / [project](https://aha-vlm.github.io/) | Failure detection, failure reasoning, temporal/trajectory context | Supports offline VLM failure auditing; not an action oracle | [To save] |
| A | RoboReward: General-Purpose Vision-Language Reward Models for Robotics (2026 preprint) | [arXiv](https://arxiv.org/abs/2601.00675) / [benchmark](https://crfm.stanford.edu/helm/robo-reward-bench) | Success, failure, near-miss, and partial-progress reward modeling | Supports weak visual supervision and audit signals; verify final venue | [To save] |

## 4. Shared Autonomy, Residuals, Corrections, And Iterative Learning

| Priority | Work | Link | What to extract | Relation to our work | Local Zotero |
|---|---|---|---|---|---|
| A | Residual Reinforcement Learning for Robot Control (ICRA 2019) | [DOI](https://doi.org/10.1109/ICRA.2019.8794127) | Residual policy on top of an existing controller | Theoretical precedent for bounded local corrections; different objective and training signal | [Present] |
| A | Shared Autonomy via Hindsight Optimization (RSS 2015) | [DOI](https://doi.org/10.15607/RSS.2015.XI.032) | Combining human commands with autonomous assistance | Supports preserving human authority while adding assistance | [Present] |
| A | DAgger: A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning (AISTATS 2011) | [PMLR](https://proceedings.mlr.press/v15/ross11a.html) | Expert querying on learner-induced states | Training/data-collection paradigm; not the paper's primary outcome | [Verify] |
| A | ThriftyDAgger: Budget-Aware Imitation Learning (CoRL 2021) | [arXiv](https://arxiv.org/abs/2109.08273) / [PMLR](https://proceedings.mlr.press/v164/) | Expert-budget allocation and intervention efficiency | Closest budget-aware interactive-learning baseline | [To save] |
| A | Robot Learning on the Job: Human-in-the-Loop Autonomy and Learning During Deployment (RSS 2023) | [DOI](https://doi.org/10.15607/RSS.2023.XIX.005) | Human interventions during deployment and continual improvement | Supports intervention-based data loops; differs in target outcome | [Present] |
| A | HIL-SERL: Human-in-the-Loop Reinforcement Learning for Robot Manipulation (CoRL 2024) | [project](https://hil-serl.github.io/) | Human intervention and recovery for manipulation | Useful comparison for corrective data, but it optimizes RL policy performance | [To save] |

## 5. Algorithm Foundations And Mathematical Sources

These papers are the reading index for rewriting Method. The archival source and
the download link are listed separately; an arXiv version is not treated as a
substitute for the formal publication record.

| Concept | Exact paper | Formal venue/source | arXiv or download | What to define in Method | Local Zotero |
|---|---|---|---|---|---|
| Conditional latent-variable modeling | Auto-Encoding Variational Bayes | ICLR 2014 | [arXiv:1312.6114](https://arxiv.org/abs/1312.6114) | ELBO, prior/posterior, reparameterization, KL term | [待保存] |
| Causal sequence modeling | Attention Is All You Need | NeurIPS 2017 | [arXiv:1706.03762](https://arxiv.org/abs/1706.03762) | scaled dot-product attention and causal mask | [待保存] |
| Interactive imitation learning | A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning (DAgger) | AISTATS 2011, PMLR 15 | [PMLR](https://proceedings.mlr.press/v15/ross11a.html) | learner-induced states, expert query, distribution shift | [需核验] |
| Budgeted expert intervention | ThriftyDAgger: Budget-Aware Novelty and Risk Gating for Interactive Imitation Learning | CoRL 2021, PMLR 164 | [arXiv:2109.08273](https://arxiv.org/abs/2109.08273) / [PMLR volume](https://proceedings.mlr.press/v164/) | intervention budget and risk/novelty gating | [待保存] |
| Residual control | Residual Reinforcement Learning for Robot Control | ICRA 2019 | [DOI](https://doi.org/10.1109/ICRA.2019.8794127) | bounded correction on top of a base controller | [Present] |
| Shared autonomy | Shared Autonomy via Hindsight Optimization | RSS XI 2015 | [DOI](https://doi.org/10.15607/RSS.2015.XI.032) | human/autonomy action combination and authority | [需核验] |
| Deployment-time correction | Robot Learning on the Job: Human-in-the-Loop Autonomy and Learning During Deployment | RSS XIX 2023; IJRR 2025 | [RSS DOI](https://doi.org/10.15607/RSS.2023.XIX.005) / [IJRR DOI](https://doi.org/10.1177/02783649241273901) | intervention data and continual update loop | [Present] |
| Human-in-the-loop recovery | HIL-SERL: Human-in-the-Loop Reinforcement Learning for Robot Manipulation | CoRL 2024 | [project](https://hil-serl.github.io/) | corrective intervention and recovery supervision | [待保存] |

## 6. Formal Publication Audit For Other Candidates

This audit records the strongest publication source currently verified for the
remaining literature. “Preprint only” is intentional: it means no archival
venue was confirmed in the local audit as of 2026-09-06.

| Work | Formal publication source | Download / full text | Status |
|---|---|---|---|
| GELLO | IROS 2024, DOI [10.1109/IROS58592.2024.10801581](https://doi.org/10.1109/IROS58592.2024.10801581) | [arXiv:2309.13037](https://arxiv.org/abs/2309.13037) | Archival verified |
| Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware (ALOHA) | RSS XIX 2023, DOI [10.15607/RSS.2023.XIX.016](https://doi.org/10.15607/RSS.2023.XIX.016) | [arXiv:2304.13705](https://arxiv.org/abs/2304.13705) | Archival verified |
| Universal Manipulation Interface (UMI) | RSS XX 2024, DOI [10.15607/RSS.2024.XX.045](https://doi.org/10.15607/RSS.2024.XX.045) | [arXiv:2402.10329](https://arxiv.org/abs/2402.10329) | Archival verified |
| DROID | RSS XX 2024 proceedings | [project](https://droid-dataset.github.io/) / [RSS proceedings](https://roboticsproceedings.org/rss20/) | Proceedings page verified; DOI to check before submission |
| Mobile ALOHA | No archival venue confirmed in this audit | [arXiv:2405.02292](https://arxiv.org/abs/2405.02292) | Preprint / venue check |
| Holo-Dex | No archival venue confirmed in this audit | [arXiv:2210.06463](https://arxiv.org/abs/2210.06463) / [project](https://holo-dex.github.io/) | Preprint / venue check |
| AnyTeleop | No archival venue confirmed in this audit | [arXiv:2403.07870](https://arxiv.org/abs/2403.07870) | Preprint / venue check |
| DexCap | RSS XX 2024, DOI [10.15607/RSS.2024.XX.043](https://doi.org/10.15607/RSS.2024.XX.043) | [RSS DOI](https://doi.org/10.15607/RSS.2024.XX.043) | Archival verified |
| Open-TeleVision | No archival venue confirmed in this audit | [arXiv:2407.01512](https://arxiv.org/abs/2407.01512) / [project](https://robot-tv.github.io/) | Preprint / venue check |
| ARCap | No archival venue confirmed in this audit | [arXiv:2609.02455](https://arxiv.org/abs/2609.02455) / [project](https://stanford-tml.github.io/ARCap/) | Preprint / venue check |
| EgoDex | ICLR 2026 (verify final proceedings record) | [arXiv:2505.11709](https://arxiv.org/abs/2505.11709) / [code](https://github.com/apple/ml-egodex) | Venue reported; proceedings check |
| EgoMI | No archival venue confirmed in this audit | [arXiv:2511.00153](https://arxiv.org/abs/2511.00153) / [project](https://egocentric-manipulation-interface.github.io/) | Preprint / venue check |
| Robot Data Curation | RSS XXI 2025, DOI [10.15607/RSS.2025.XXI.023](https://doi.org/10.15607/RSS.2025.XXI.023) | [RSS DOI](https://doi.org/10.15607/RSS.2025.XXI.023) | Archival verified |
| RINSE | No archival venue confirmed in this audit | [arXiv:2604.23000](https://arxiv.org/abs/2604.23000) | Preprint only |
| RoboMimic | CoRL 2021, PMLR 164 | [arXiv:2108.03298](https://arxiv.org/abs/2108.03298) / [PMLR volume](https://proceedings.mlr.press/v164/) | Archival volume verified |
| MimicGen | CoRL 2023, PMLR 229 | [arXiv:2310.17596](https://arxiv.org/abs/2310.17596) / [PMLR volume](https://proceedings.mlr.press/v229/) | Archival volume verified |
| DexMimicGen | ICRA 2025 venue requires proceedings/DOI check | [arXiv:2410.24185](https://arxiv.org/abs/2410.24185) | Venue check |
| AHA | No archival venue confirmed in this audit | [arXiv:2410.00371](https://arxiv.org/abs/2410.00371) / [project](https://aha-vlm.github.io/) | Preprint only |
| RoboReward | No archival venue confirmed in this audit | [arXiv:2601.00675](https://arxiv.org/abs/2601.00675) / [benchmark](https://crfm.stanford.edu/helm/robo-reward-bench) | Preprint only |
| DexUMI | No archival venue confirmed in this audit | [arXiv:2505.21864](https://arxiv.org/abs/2505.21864) | Preprint only |
| Data Pyramid for Embodied Manipulation | No archival venue confirmed in this audit | [arXiv:2607.24744](https://arxiv.org/abs/2607.24744) | Survey preprint |

## 7. Suggested Reading Order

Read and save these first (roughly 20 papers):

1. GELLO, ALOHA, UMI, DROID, ARCap, EgoDex.
2. Robot Data Curation, RINSE, RoboMimic, MimicGen.
3. AHA, RoboReward, SuccessVQA, one additional full-episode VLM audit paper.
4. Residual RL, Shared Autonomy via Hindsight Optimization, DAgger, ThriftyDAgger, Robot Learning on the Job, HIL-SERL.

For every saved item, record one exact passage, page/section, DOI or archival
URL, and the claim it supports. Do not copy abstract language into the paper
as if it were our experimental conclusion.

## 8. Evidence Card Template

```text
Title:
Authors / year / venue:
DOI or archival URL:
Data source and embodiment:
What is labeled or audited:
Method mechanism:
Main reported result:
Exact supporting quote:
Page / section / figure:
What the paper does not solve:
Relation to our continuous visual filter:
BibTeX key after Zotero import:
```

Items marked `search` or `verify` are deliberately not yet suitable for the
submission bibliography. They are leads for Zotero retrieval, not confirmed
citations.
