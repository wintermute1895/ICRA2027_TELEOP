---
title: "Reference-Anchored Corrective Data Flywheel for Locally Recoverable Precision Insertion"
status: "living draft - claims are hypotheses until experiments close them"
updated: 2026-08-12
target: "ICRA 2027 candidate"
---

# Paper Draft: Locally Recoverable Insertion

> 工作规则：本文档每一段主张都必须对应一个可证伪实验和一个文献证据卡。不能因为已有
> 工程能力就把它写成 contribution。`[OPEN]` 表示需要与 PI/团队确认；`[REVIEWER]` 是
> 预期攻击；`[KILL]` 是足以砍掉当前主张的结果。

## Decision Log

| Date | Decision | Status | Consequence |
|---|---|---|---|
| 2026-08-12; amended 2026-08-14 | Treat reference-aligned recovery-frontier collection (RFC) as the algorithmic candidate, while retaining reference-conditioned residual recovery (C1) as the minimum viable paper. | pending team confirmation | Build common C1 infrastructure first; RFC must not determine the title or abstract results claim until it clears all matched allocation/gating controls. This includes A0, B2, I0, T0, U0, B3-no-z, B3-no-rec, and a CRSAIL-style representation-novelty control if the team chooses a broad active-query comparison. |
| 2026-08-12 | DPIIL RA-L 2024 was fully inspected and directly covers safe precision-aware interactive imitation learning for clearance-limited tasks. | evidence accepted | RFC may no longer claim online safety querying, precision-aware intervention, or generic data-efficient clearance-limited IIL. |
| 2026-08-12 | PhaForce (arXiv:2603.08342) was inspected through arXiv HTML full text. | evidence accepted | It covers contact-aware phase belief, slow planning, phase-routed high-rate residuals, USB insertion, rim collision, partial insertion, retreat/retry, F/T feedback and OOD geometry. PAR is not a viable primary contribution. |
| 2026-08-12 | Geometric-reference conditioned policy scan completed. | evidence supports narrowing, not a uniqueness claim | No identical top-venue formulation was verified, but Residual RL, residual assembly work, adaptive insertion IL, AutoMate, and PhaForce mean C1/reference-plus-residual is a baseline capability, not an algorithmic contribution. |

**[OPEN: answer required before confirmatory collection]** Choose one: (A) invest in RFC as the primary
algorithmic claim, with its explicit kill criterion; or (B) commit to C1 as a systems/empirical paper and register RFC
only as an exploratory protocol. The former PAR branch is closed by PhaForce evidence. Until answered, use the
dual-track wording below.

**Research decision after adversarial review.** The paper has only one remaining plausible algorithmic claim: RFC's
cross-round allocation of a fixed corrective budget. C1 is indispensable infrastructure and an experimental baseline,
not a new learning algorithm. PAR is closed. If RFC does not survive its DPIIL-style and reactive-DAgger controls,
the honest fallback is a benchmark/systems paper about an auditable reference-anchored precision-insertion data and
evaluation protocol. That fallback is publishable only if it offers genuinely useful assets: standardized episode
contracts, perturbation/visibility/contact splits, reproducible simulation-to-real semantic checks, and a result that
random episode splits materially overestimate recovery performance. It must not be advertised as an algorithm paper.

**Recommended course: a bounded RFC viability pilot, then commit.** Do not choose between an algorithm paper and a
benchmark paper by taste. Run one simulation-only pilot before scaling real collection. Use one insertion geometry,
one fixed nominal reference, one seeded safety-valid candidate pool, one disjoint seeded held-out target distribution,
one shared safety gate, and one fixed policy architecture. The primary controls are A0/random candidate allocation,
B2/reactive DAgger, I0/DPIIL-style precision-risk query, T0/ThriftyDAgger-style novelty-risk gating, U0/generic
uncertainty-coverage allocation, B3-no-z, and B3/RFC. Add `C0`/CRSAIL-style post-rollout representation novelty if
the paper makes any comparison beyond the declared LRI allocation family. In the initial simulation-only stage, match oracle queries,
corrected horizons, reset behavior, rollout count, accepted frames, and training seeds; do not relabel oracle compute
time as human time. Match active human-correction seconds only after a human-in-the-loop stage. If RFC's grouped-
bootstrap interval for held-out recovery per oracle-query/corrected horizon does not clear its required controls, stop
RFC development and immediately adopt the evaluation/systems paper path. A positive pilot does not prove the final
contribution, but earns the right to collect the three-task data; a negative pilot prevents months of engineering on a
claim that cannot survive review.

## 0. One-Sentence Thesis

We study **locally recoverable precision insertion**: tasks with a feasible nominal reference but bounded pose,
perception, and contact deviations. We investigate whether reference-conditioned residual policies trained from
targeted corrective demonstrations improve recovery on held-out perturbations more efficiently than executing the
reference or learning actions from demonstrations without the reference. Simulation pilots use a disclosed correction
oracle; claims about human demonstration efficiency require separate real-teleoperation evidence.

中文工作表述：对存在可行名义参考、但因有限扰动、间歇可见和局部接触偏差而失效的精密插入，
我们研究如何以名义参考为锚，从策略失败状态附近采集人工纠偏，学习受安全约束的局部残差策略。

## 1. Problem Boundary And Task Taxonomy

### 1.1 Formal task family

定义任务族 `LRI`（locally recoverable insertion）。一个 episode 属于 `LRI`，当且仅当：

1. **Nominal feasibility**：给定目标几何与标定，存在无碰撞、满足关节/速度约束的名义参考
   \(\xi^{ref}_{0:T}\)。
2. **Bounded deviation**：真实状态相对参考的归一化偏差 \(d(\delta)\) 位于预先验证的恢复域
   \(\mathcal R_\tau\) 内；归一化以装配 clearance、容许姿态误差和可用安全裕度定义，而不是
   任意称为“小扰动”。
3. **Intermittent observability**：在长度不超过 \(H_{occ}\) 的遮挡内，机器人本体状态、最后可见
   目标状态和/或接触证据足以选择安全退回或维持；遮挡解除后可重观测目标相对状态。
4. **Finite local contact modes**：接近、预插入、首次接触、受约束插入/滑移、seated、退回重试这些
   局部模式可在事后由任务结果、外部成功传感或额外接触证据标注，且任务有可观测的成功/失败判据；它们
   不被假定为当前 RGB-D/kinematic 栈可实时区分的控制状态。

这借鉴 contact trust-region 的边界逻辑：局部模型只能在经验证的局部域内用于改进，超出域时不应
声称局部控制可解决全局问题。我们不会声称学习了完整接触动力学或拥有 CTR 的理论保证。

### 1.2 Task axes and coverage matrix

| Axis | Levels | Measurement | Why this is a boundary |
|---|---|---|---|
| nominal geometry | peg / USB-C / RJ45 | insertion axis, clearance, rotational constraint, terminal condition | Avoids a single-axis, single-object claim |
| normalized geometric deviation | in-domain low / medium / boundary; out-of-domain | translation / clearance, orientation / tolerance | Tests a recovery region rather than arbitrary noise |
| observability | visible / short occlusion / re-observable; persistent occlusion | visibility ratio, occlusion duration, re-acquisition latency | Separates closed-loop recovery from blind insertion |
| contact state | pre-contact / initial-contact / constrained insertion / retreat-retry | phase/event labels | Separates approach planning from contact recovery |
| data provenance | nominal demo / corrective intervention / unsuccessful recovery | policy state, operator intervention, final outcome | Makes data selection causally testable |

Coverage is defined as occupied cells of this matrix, not episode count. Training and test splits must be grouped by
episode/session/operator; frames from one episode may never appear in both sets. At least one of geometry instance,
perturbation combination, or contact/recovery pattern is held out.

### 1.3 Explicit exclusions

- No global planning from an infeasible reference.
- No persistent full occlusion or blind insertion without vision/contact/state evidence.
- No guarantee for irreversible jamming, unsafe contact forces, workspace violations, or unknown connector geometry.
- No claim that human kinematics reveals human intent.
- No generic assembly claim from only one insertion axis or one object geometry.

### 1.4 Corner-case protocol

| Case | Required system behavior | Label |
|---|---|---|
| reference infeasible | reject before execution or request replan | `reference_invalid` |
| deviation outside \(\mathcal R_\tau\) | stop advance, retreat/reobserve, or request intervention | `out_of_recovery_region` |
| short occlusion | do not advance without state-consistent safe action; re-align after view returns | `temporary_occlusion` |
| persistent occlusion | no blind progress claim; stop/retreat/request intervention | `persistent_unobservability` |
| contact jam / skew | bounded retreat and retry; record recovery outcome | `contact_recovery` |
| high jerk but successful recovery | retain, do not delete due to smoothness alone | `valid_abrupt_recovery` |
| smooth but unsuccessful behavior | low learning utility despite smoothness | `smooth_failure` |
| high-confidence failure | calibration failure, queue for correction | `miscalibrated_proposal` |

## 2. Draft Abstract

Precision insertion often admits a geometric reference trajectory in a nominal scene, yet fails under small target
pose errors, intermittent visibility, and contact deviations. End-to-end imitation learning requires demonstrations
over this failure distribution, while model-only execution cannot recover from errors absent from its nominal model.
We formulate locally recoverable precision insertion as execution around a feasible reference within a bounded,
intermittently observable recovery region. We study reference-conditioned local residual recovery and evaluate whether
a feasible reference improves robustness over nominal execution and reference-free behavior cloning under
pre-registered geometry, perturbation, visibility, and contact-mode splits. We further investigate a
reference-aligned recovery-frontier collection rule that allocates teleoperated corrective effort using immutable
*prior-round* outcome evidence, pre-query safety/feasibility features, and declared target-cell coverage rather than
smoothness alone. [OPEN: RFC is an experimental
hypothesis, not a completed contribution. Insert results only after E1/E3 complete; do not claim data efficiency or
real-robot generalization until measured.]

## 3. Introduction Skeleton

### Paragraph 1: Practical problem

USB-C, RJ45, and peg insertion have known completion geometries, so nominal motion planning is useful. Their hard
part is not selecting an abstract goal but correcting local deviations near contact when perception is imperfect and
the nominal path no longer suffices.

### Paragraph 2: Gap

Pure planning has brittle local model/perception assumptions; pure visuomotor imitation must cover failures the
nominal demonstrations do not visit. Generic teleoperation datasets may contain large amounts of approach motion
but underrepresent the corrective segments that decide insertion success.

### Paragraph 3: Central hypothesis

Use a feasible reference as a structured prior. Learn only local corrective actions around it, then collect more data
where the current policy violates recovery or quality criteria. This is not goal/intent inference and not global
motion planning.

### Paragraph 4: Boundary and contributions

State LRI boundary and three candidate contributions below. Mention that the paper deliberately refuses persistent
blind insertion and infeasible-reference cases.

### Draft contributions (conditional)

1. A formal LRI task/coverage protocol based on nominal feasibility, normalized recovery region, observability and
   contact mode, with explicit out-of-scope failure behavior.
2. A reference-conditioned residual learning and corrective-aggregation loop for local recovery, with a safety
   projection between learned action and execution.
3. A result-aware data valuation protocol that tests, at fixed collection budget, whether selection/targeted
   recollection improves held-out recovery rather than merely smoothness.

**Contribution status after literature challenge.** Item 2 is a required comparison, not a novel contribution. Item 3
is the only remaining algorithmic candidate, and must be narrowed to RFC's *cross-round allocation* claim. Item 1 can
be a contribution only as a released and used evaluation protocol, not as prose taxonomy.

### Proposed final contribution wording (conditional)

The boundary is now sufficiently precise to state contributions, but not to assert an algorithmic result before the
pre-registered comparison. The final Introduction should use one of the following two claim sets, selected by the RFC
viability gate rather than by preference.

**Algorithm-paper path, only if RFC passes.**

1. We formulate **locally recoverable precision insertion (LRI)** as reference-feasible insertion under normalized
   local deviation, bounded re-observable visibility, and labelled contact/recovery modes; we release an auditable
   episode contract and grouped split protocol for this setting.
2. We introduce **reference-aligned recovery-frontier collection (RFC)**, a cross-round allocation rule that spends a
   fixed correction budget over reference-progress and deviation cells using observed recoverability, coverage, and
   shared safety feasibility.
3. We show, under matched correction budget and a shared online safety gate, whether RFC improves held-out recovery
   over reactive DAgger, precision/risk-triggered IIL, ThriftyDAgger-style gating, random allocation, generic
   uncertainty/coverage allocation, its no-progress ablation, and (when claiming beyond LRI) CRSAIL-style
   representation novelty; we separately report simulation-oracle and human-correction evidence.

**Systems/evaluation path, if RFC fails.**

1. We provide the same LRI episode contract, task axes, perturbation/visibility/contact splits, and sim-to-real
   semantic checks for auditable precision-insertion data collection.
2. We establish a **planner-versus-learned-recovery capability map**: across a predeclared reference-relative error,
   observability, and recovery-outcome grid, determine where reference-only execution and relocalize-and-replan
   suffice, where reference-conditioned residual recovery adds value, and where every available method must abstain.
3. We show that a conventional IID episode score is insufficient to choose between M0 replan and B1 residual recovery
   unless it predicts this capability map on held-out recovery cells; smoothness filtering and outcome-unaware
   aggregation are reported only as secondary diagnostics.

**[REVIEWER GATE]** The systems/evaluation wording is defensible only if the capability map changes a deployment
choice: e.g., M0 is sufficient in a measurable region, B1 adds recovery in another, and both abstain outside a
declared boundary. The algorithm wording is defensible only if RFC beats every required allocation/gating control at
the same budget. A boundary alone is neither a contribution nor evidence of novelty.

**Reviewer correction: random splitting is not itself novelty.** Grouping examples by episode/session and holding out
task variants is established benchmark hygiene (e.g., FurnitureBench). We must not claim that random splitting is a
newly discovered problem. The potentially publishable evaluation question is narrower: an IID, episode-grouped split
and a **reference-relative recovery-cell split** estimate different target risks. The former estimates repeatability
over a familiar mixture; the latter estimates recovery after a declared perturbation/contact/visibility combination
has been withheld. This becomes a contribution only if the difference changes a method ranking or a deployment
decision under a fixed task distribution, and if the recovery-cell split is precisely constructible from released
metadata. Otherwise it remains required evaluation hygiene.

**[OPEN FOR TEAM DISCUSSION]** If RFC fails, shall the systems/evaluation thesis be: “standard IID evaluation fails to
predict the planner-versus-learned-recovery capability map in reference-anchored insertion”? This is stronger than
“random splits are optimistic,” because it must alter a real controller selection/abstention decision. It requires a
controlled region in which M0 and B1 differ, not merely a small average-score gap. Smoothness-filter loss and
sim-to-real semantic mismatch remain secondary diagnostic studies unless they independently meet the same bar.

### Contribution gate: what can actually be claimed

The task boundary makes the claim *testable*; it does not itself make a method novel. We must distinguish three
levels before writing the final contribution list.

| Level | Candidate claim | What is already known / reviewer objection | Minimum proof to retain it | Status |
|---|---|---|---|---|
| C0: problem and protocol | LRI gives a falsifiable task boundary and coverage/split protocol for reference-feasible, locally recoverable insertion | “This is only a taxonomy.” | At least three geometries, all declared axes, OOD abstention, and reproducible recovery-region calibration. | Retain only if the protocol reveals a failure hidden by conventional random episode splits. |
| C1: reference-conditioned recovery | Reference-conditioned residual learning improves local recovery over reference-only and reference-free BC. | Residual control and BC are established; this may be a known composition. | B1 must beat A and B0 on held-out perturbation/contact/visibility cells with no safety regression. | Mandatory empirical claim, but not sufficient algorithmic novelty alone. |
| C2: correction allocation | A reference-aligned, *cross-round fixed-candidate budget allocation* rule improves target-weighted recovery on a disjoint held-out target distribution. | DAgger, DexCap/Tilde, DPIIL, ThriftyDAgger, CRSAIL and generic active selection already query, gate, or select corrections; candidate-pool construction can explain gains. | B3 must beat A0/B2/I0/T0/U0 at matched oracle-query budget in simulation and matched operator time on a reproducible physical pool in human studies; B3-no-z is required for a progress-specific claim and B3-no-rec for recovery-frontier/recoverability-aware wording. `C0`/CRSAIL-style representation novelty is additionally required for any claim beyond the declared LRI allocation family. | High-risk candidate only. Drop it if the gain is absent, selected-pool-only, or explained by gating/exposure. |
| C3: recoverability-aware execution | An empirically calibrated local recovery boundary decides residual scale, retreat/reobserve, and intervention, reducing unsafe/fruitless attempts without hiding failures. | A threshold is hand tuning; CTR and robust control already address local contact validity. | Calibrated risk-coverage/abstention evaluation, plus comparison to fixed thresholds and an available model-based local-recovery baseline. | Optional and high risk; retain only if calibration works. |

**Current recommended claim hierarchy.** Do not advertise C1 as a new algorithm by itself. The core contribution
should be **C2**, conditional on an actual equal-budget improvement: *a recovery-aware corrective data allocation
rule for reference-anchored precision insertion*. C0 makes that evaluation credible; C1 is the necessary capability
demonstration; C3 is a safety/validity extension only if it survives calibration.

**Working C2 formulation: reference-aligned recovery-frontier collection (RFC).** This is a hypothesis, not yet a
paper title. RFC must be understood as an *offline/cross-round allocation policy*, not an online safety-intervention
rule. Online safety gating is shared by every condition and is not claimed as RFC novelty. Its query-time state is
\(\psi_t=(z_t,\hat\delta_t,v_t,h_t)\): reference-progress bin \(z_t\), deviation from the reference in the local
insertion frame \(\hat\delta_t\), pre-query observability/validity features \(v_t\), and a history summary \(h_t\)
from completed earlier rollouts. The deviation is normalized by task clearance and angular tolerance. Current
contact/recovery outcome \(c_t\) and correction success are **post-query labels**, never inputs used to score the
same unexecuted candidate. RFC maintains empirical recovery, abstention, and correction statistics from completed
cells and uses them only in a later round. With a fixed human-time budget, it prioritizes *safe, informative*
candidates near the empirical recovery frontier: cells with uncertain or declining recovery probability,
insufficient coverage, and a valid correction path. States outside the safety region are labelled/rejected, not
intentionally explored by a learned policy.

RFC is distinct from ordinary failure-only DAgger and precision/risk-triggered IIL only if all of the following are true:

1. it allocates collection over **reference-relative progress/deviation cells**, rather than accepting every observed
   failure equally;
2. it uses **historical outcome-labelled recoverability** to distinguish a candidate resembling past correctable
   local failures from an infeasible or unsafe state; it never sees the new candidate's recovery outcome before
   selection;
3. its objective is **equal-budget held-out recovery coverage**, not just post-hoc trajectory filtering; and
4. it allocates a fixed **future collection budget across candidate cells/rounds**, rather than deciding only when to
   cede control within the current rollout; and
5. it is compared against reactive DAgger and a DPIIL-style precision/risk-triggered intervention baseline.

These conditions are necessary but not sufficient. They only distinguish RFC from the most direct corrective-IIL
precedents. A second reviewer objection is more fundamental: “this is generic uncertainty/coverage active learning
expressed in a manually chosen insertion coordinate.” Therefore, RFC must also be compared with a generic
uncertainty-plus-coverage allocator on a matched, non-reference state partition (`U0`), a random safety-valid
candidate allocator (`A0`), an RFC ablation without reference progress (`B3-no-z`), and a reference-stratified
coverage-only ablation without historical recoverability (`B3-no-rec`). The `U0` partition must have
the same number of cells, update schedule, candidate-pool access, shared oracle and budget. If `B3` does not beat
`U0`, it supports active collection at most, not reference-aligned allocation. If it does not beat `B3-no-z`, it
supports reference-relative deviation but not the stronger phase/progress claim. If it does not beat `B3-no-rec`, it
supports at most reference-stratified coverage allocation, not a recovery-frontier claim based on historical outcomes.

The score may begin transparent rather than learned:
\[
q(\psi)=\mathbb{1}[\text{safe}(\psi)]\;\mathbb{1}[\text{correction-valid}(\psi)]
\bigl(\lambda_u U(\widehat p_{rec}(\psi))+\lambda_g G(\psi)+\lambda_f F(\psi)\bigr),
\]
where \(U\) is uncertainty around a *historical* empirical recovery estimate, \(G\) is unfilled coverage-cell value,
and \(F\) derives only from prior failed or safety-invalid outcomes. The score is an operational baseline, **not a
theoretical utility function**. A learned score is justified only after this transparent version beats its ablations.

**[REVIEWER: does “frontier” do any work?]** `B3-no-rec` must retain the same \((z,\hat\delta,v)\) cells, target
weights, candidate pool, safety gate, coverage term \(G\), round schedule, correction budget and deterministic tie
breaking as B3, but sets every history-derived recoverability/uncertainty/failure term to zero. It may not use
previous correction success, failure, abstention or contact/recovery outcomes to rank future cells. Thus B3 versus
`B3-no-rec` identifies the incremental value of **historical recovery outcomes**, conditional on reference
stratification and coverage. If this contrast is null or negative, remove “recovery-frontier,” “recoverability-aware
allocation,” and any claim that outcomes improve selection; retain only the weaker reference-stratified coverage
diagnostic if it separately clears its stated controls.

**Theoretical status.** RFC is currently a finite-candidate, safety-constrained active experimental-design rule over
reference-aligned recovery cells. It is not yet a contextual-bandit algorithm, Bayesian-optimization method, or
manifold-learning result: no stochastic reward model, exploration policy, regret notion, or coverage theorem has been
specified. The empirical claim is therefore comparative allocation efficiency under a declared candidate pool and
budget. A theory claim would require, at minimum, a formal candidate distribution, an observable reward/recovery
model, an information or utility objective, and assumptions under which the proposed score has a bound or consistency
result. Until those are supplied and tested, do not invoke the manifold hypothesis, low-dimensional structure, regret,
or optimality as justification for RFC.

**Method correction: formulate RFC as pre-registered stratified allocation, not a discovered utility.** Let
\(\mathcal C=\{c\}\) be the finite safe candidate cells obtained from the fixed pool using only
\((z,\hat\delta,v)\), let \(w_c\) be a frozen target-distribution weight, and let \(n_c\) be the number of future
correction opportunities assigned to cell \(c\) in round \(r\). RFC must disclose the deterministic rule producing
\(n^{(r)}\) under \(\sum_c n_c\le B_r\), per-cell safety/repeatability constraints, and prior-round immutable
outcomes. Its evaluation target is not score maximization but held-out weighted recovery risk
\(R_w(\pi)=\sum_c w_c\Pr[\mathrm{failure}\mid c,\pi]\), together with all-attempt abstention/safety accounting.
This makes the method reproducible and makes its assumptions visible: the cell partition and weights encode the
declared deployment target. It does **not** establish that these weights, cells, or the allocation rule are optimal.
The transparent \(q\) score is therefore a pre-registered *allocation policy* whose only justification is a matched
downstream result, not an information-theoretic utility.

**[REVIEWER UPDATE: offline selective querying is prior art.]** CRSAIL (arXiv:2512.00453, official abstract checked)
already rolls out complete learner episodes and subsequently queries an expert only at selected visited states using
dataset-representation/novelty scores; it explicitly argues that this avoids real-time takeovers. RND-DAgger (ICLR
2025, arXiv:2411.01894) uses state OOD to decide expert interventions. Thus RFC must not claim post-rollout query
selection, novelty/coverage querying, query-rate reduction, or no-real-time-takeover collection as new. The required
distinction is narrower: a fixed, physically reproducible **reference-relative stratification** whose target weights
and safety envelope are declared before data collection, tested against a matched non-reference partition `U0` and
against CRSAIL-style representation novelty when feasible. If the project cannot implement the latter, state that RFC
is only compared within the declared LRI allocation family and make no broad query-efficiency claim.

**[REVIEWER: selected-pool versus deployment distribution]** RFC deliberately changes which recovery cells enter
training. A gain on its own selected candidates is selection bias, not evidence of robust deployment. The primary
test distribution must therefore be constructed *before* collection, be disjoint from the adaptively selected
candidate opportunities, and be identically seeded/stratified across all conditions. Report three distinct
quantities: (i) success on the fixed held-out target distribution, (ii) coverage and outcome of the selected pool,
and (iii) performance under a separately reported natural/uncontrolled rollout distribution, if measured. The first
supports only the declared target distribution; the third cannot be inferred from it. RFC may not claim it models or
optimizes the natural failure distribution, because the physical candidate pool is an experimental intervention, not
an observational sample of deployment failures.

**[REVIEWER: what is the experimental unit?]** A bootstrap over held-out episodes from one trained policy does not
establish that the *collection rule* caused the gain. The rule changes data composition; candidate-pool generation,
initial data, policy optimization, train/validation split, and held-out target sampling can each create a spurious
ordering. The causal experimental unit is therefore an **outer collection trial** \(k\), not a frame and not merely a
test episode. Trial \(k\) fixes one initial dataset, one safety-valid seeded candidate pool, one disjoint validation
set and one disjoint target set. Every primary condition receives the same trial assets and the same declared
correction budget, then trains with a paired list of optimizer seeds. The primary treatment contrast is the paired
outer-trial difference in target-weighted recovery risk,
\[
d_{k,j}=R_w(\pi_{k,j})-R_w(\pi_{k,B3}),\quad j\in\{A0,B2,I0,T0,U0,B3\text{-no-}z,B3\text{-no-rec}\},
\]
where lower \(R_w\) is better. Report the distribution and a trial-level paired bootstrap/paired randomization
interval over \(d_{k,j}\), with target-episode bootstrap nested inside each trial only as a precision diagnostic. A
single policy seed, a single candidate-pool seed, or frame-level resampling cannot support a collection-method claim.

**Data-accounting requirement.** Match both the intervention resource and the learner input. For every condition and
outer trial, log: candidate opportunities exposed; attempted, rejected and corrected queries; corrected horizon;
unique accepted episodes; unique action frames; duplicated/replayed frames; training updates; and wall-clock/oracle
calls. “Same query count” is not sufficient if one condition produces longer corrections or more accepted frames;
“same accepted frame count” is not sufficient if one condition discards many more difficult attempts. The primary
estimate uses the fixed correction budget and all-attempt safety denominator; a second, explicitly labelled
fixed-training-frame analysis may diagnose whether an effect is due to data composition rather than volume. Do not
downsample away hard failures to force equality without retaining them in the all-attempt audit.

**Tuning firewall.** The held-out target distribution is used once for the final comparison only. Define score weights,
cell boundaries, safety thresholds, model architecture, and training schedule before collection; tune them only on a
separately seeded validation distribution shared by all conditions. Any change after observing target results is an
amendment that restarts the confirmatory comparison. This also applies to choosing \(\lambda_u,\lambda_g,\lambda_f\),
the correction horizon, and the number of cells.

**[REVIEWER]** “This is simply DAgger with bins and thresholds, or DPIIL with a different risk score.”

**Required answer:** In simulation, RFC must demonstrate higher held-out recovery success per matched oracle
query/corrected horizon than reactive DAgger and DPIIL-style risk-triggered IIL at matched initial data, rollout
budget, safety region, and training recipe. A later human study must reproduce the ordering at matched active operator
time before any human-efficiency claim. Otherwise call RFC an analysis protocol, not a method contribution. Tilde
already collects a DAgger trajectory after a policy failure; DexCap already supports online residual correction and
stores it for fine-tuning; DPIIL already uses demonstrator-perceived precision and policy uncertainty to request safe
human intervention in clearance-limited tasks. None may be described as absent.

**[REVIEWER: ThriftyDAgger challenge]** ThriftyDAgger (CoRL 2021 Oral; arXiv:2109.08273 official abstract verified)
already learns a budget-aware switching policy that requests human intervention at novel or low task-completion-
confidence states, and evaluates physical cable routing. Thus neither human-budget-aware novelty/risk gating nor the
timing/length of current-rollout interventions is RFC novelty. The viability pilot must include a disclosed
ThriftyDAgger-style `T0` control. For a valid allocation comparison, every condition has the same outer safety gate;
`T0` decides *when* to engage the shared correction source in a rollout, whereas RFC decides which future, fixed-pool
candidate opportunities receive the budget in the next round. If B3 does not beat T0 at the declared budget, RFC must
not be described as more data- or supervisor-efficient than budget-aware interactive IL.

**[REVIEWER]** “A reference coordinate is an engineering feature, not a new active-learning principle.”

**Required answer:** RFC must outperform the matched generic uncertainty/coverage allocator `U0`, not merely random
collection or reactive DAgger. It must additionally outperform the `B3-no-z` ablation to claim that reference
progress carries allocation value beyond reference-relative deviation. Without these results, the honest phrasing is
“we evaluated a domain-specific data allocation heuristic,” not “we propose a new collection method.” We do not
currently have a theorem that gives RFC universal optimality, regret bounds, or a uniquely derived utility; no such
claim may enter the paper.

**[REVIEWER: IntervenGen challenge]** IntervenGen (arXiv:2405.01472, HTML methods inspected) collects human-gated
mistake/recovery segments, runs the policy closed-loop to create new mistake states, randomly selects a source human
recovery, transforms it to the current object pose, interpolates and replays it open-loop, then retains only
task-successful synthetic episodes. It assumes Cartesian delta-pose actions, known object-centric subtasks, observable
object poses at subtask start during collection, and that transformed source recoveries remain valid; it identifies
F/T-assisted contact-rich adaptation as future work. It therefore closes broad “few corrections yield broad coverage”
and “interventional data generation” novelty claims. Its physical result is zero-shot block grasp under pose error,
not real contact-rich insertion.

RFC's different hypothesis is to allocate a fixed common correction source across predeclared, real, safety-valid,
physically reproducible candidates using reference-relative pre-query features and historical outcomes; it does not
synthesize or SE(3)-transform/replay correction segments. The pilot's common-oracle budget is not a fair superiority
test against I-Gen, which consumes synthetic rollouts and transformable object-centric recovery assumptions. The
final study must either implement I-Gen under a separately matched generation/interaction protocol, or explicitly
limit C2 to **selection efficiency among real correction opportunities**. Success-only filtering in I-Gen is not a
defect: it serves data generation. All-attempt failure/abstention accounting is required here only to evaluate the
allocation rule. Under no circumstance should oracle-query efficiency be reported as human-data efficiency.

**[REVIEWER: JUICER challenge]** JUICER (IROS 2024, arXiv:2404.03729, HTML methods inspected) performs backward
trajectory augmentation from demonstrations, retaining candidates that satisfy a terminal end-effector-distance
criterion, and `Collect-and-Infer`, which adds successful full policy rollouts to the dataset before retraining.
Thus RFC cannot claim novelty from focusing on high-precision bottlenecks, data augmentation, or iterative success-
rollout expansion. The inspected JUICER method does not describe reactive correction from failure states or
cross-round allocation over a fixed physical candidate pool. RFC's remaining hypothesis is therefore specific:
allocate a fixed common correction source across predeclared real, safety-valid, reproducible opportunities using
only pre-query reference-relative features and historical outcomes, while counting failures and abstentions. This is
not equivalent to JUICER's verified mechanisms, but it remains an empirical claim contingent on the full controls.

**[OPEN: central-method decision]** We should freeze whether to invest in RFC before confirmatory collection. Its
advantage is that it gives an algorithmic claim tied to precision insertion; its risk is that the score becomes a
hand-tuned generic active-learning heuristic. The viability pilot must include `A0`, `U0`, and `B3-no-z`; if the team
cannot afford those conditions, retain C1 as a clean reference-conditioned systems study and frame RFC only as a
pre-registered data protocol.

**[KILL]** If reference residual BC and ordinary DAgger match the proposed rule under equal human time, the paper
must narrow to a systems/benchmark paper or introduce a genuinely different technical mechanism. We must not claim
that collecting corrections is new.

**[REVIEWER]** “This is an engineering pipeline; what is algorithmically new?”

**Required answer:** Contribution 2 must specify a nontrivial residual representation, phase/reference alignment,
intervention query policy, or safety-constrained objective that is not merely `u_ref + BC`. If experiments show only
that a reference helps, reduce the claim to an empirical systems paper or strengthen the algorithm.

## 4. Related Work Skeleton

### 4.1 Teleoperation data collection and interactive correction

- GELLO: low-cost direct teleoperation reference.
- DexCap: multimodal dexterous data collection and interactive correction; compare sensing and correction protocol.
- UMI: portable data interface and relative trajectory representation; compare task and platform generalization.
- Tilde: most direct corrective/DAgger-style collection precedent. Distinguish its in-hand manipulation setting from
  insertion around a geometric reference.
- DAgger (Ross et al., 2011): distribution shift and iterative on-policy corrective aggregation foundation.
- ThriftyDAgger (CoRL 2021): budget-aware novelty/risk switching for current-rollout human intervention; direct
  control for any retained RFC comparison, not a component to relabel as new.

### 4.2 Residual and reference-conditioned control

- Residual Reinforcement Learning (Johannink et al., ICRA 2019): establishes model/controller plus learned residual.
- Contact Trust Region (Suh et al., IJRR 2026): supports why local contact control needs an explicit trusted region;
  we borrow boundary logic, not its contact-dynamics algorithm.
- AutoMate (RSS 2024): assembly policies across geometries; direct novelty threat for assembly generalization.
- Extended residual learning with one-shot imitation for robotic assembly (Frontiers in Neurorobotics, 2024):
  residual assembly learning novelty threat; inspect full text before any detailed comparison.
- Adaptive imitation learning for complex contact-rich insertion (Frontiers in Robotics and AI, 2022): insertion-IL
  novelty threat; inspect full text before detailed comparison.

### 4.3 Data quality, recovery, and evaluation

- What Matters in Learning from Offline Human Demonstrations: data/algorithm choices should be measured by downstream
  manipulation performance.
- RINSE: smoothness-driven quality filtering; direct challenge to smoothness-only selection.
- FurnitureBench / benchmark protocols: use compositional task factors and held-out variants, not a single easy task.
- EgoRecovery [candidate]: recovery-demonstration data collection; verify venue/method before citation.

### 4.4 Direct novelty threats found during review

- **Tilde (2024, local full text inspected):** explicitly deploys a learned policy, pauses it when a human judges it
  failed/unlikely to finish, teleoperates from the failure configuration to success, and fine-tunes with these DAgger
  demonstrations. Therefore “collect corrections from failure states” is prior art.
- **DexCap (2024, local full text inspected):** supports policy-rollout residual human correction or full
  teleoperation, stores corrected trajectories, and fine-tunes; its reported corrections improve task performance.
  Therefore “online residual human correction” is prior art.
- **JUICER (IROS 2024; arXiv:2404.03729 HTML methods inspected):** uses backward trajectory augmentation from
  demonstrations and `Collect-and-Infer`, which adds successful complete policy rollouts before retraining. It closes
  claims that local bottleneck corrections, augmented corrective data, or data-efficient precision assembly are new.
  The inspected method does not describe reactive correction from failure states or cross-round allocation over a
  fixed physical candidate-state pool. RFC may therefore be differentiated only as allocation of a common correction
  source over real, safety-valid, reproducible candidates in reference-relative coordinates, with all outcomes and
  abstentions audited; this remains an empirical hypothesis, not a novelty assertion.
- **IntervenGen (arXiv:2405.01472, HTML methods inspected):** expands human-gated corrections by closed-loop policy
  mistake generation plus random object-pose-transformed, open-loop replay of source recovery segments; it retains
  only successful synthetic episodes. It assumes known object-centric subtasks, collection-time object poses, and
  transformable valid recoveries, and identifies F/T-assisted contact-rich adaptation as future work. It closes
  generic intervention-generation/data-efficiency claims. RFC is only selection over a fixed, safety-valid,
  physically reproducible candidate pool, with no correction synthesis; comparisons require a separately matched
  generation/interaction protocol and must not describe oracle-query efficiency as human efficiency.
- **DPIIL (Oh and Matsubara, RA-L 2024, full text inspected):** learns demonstrator-perceived precision from the
  human speed-accuracy trade-off, multiplies it with policy uncertainty to estimate collision risk, and requests human
  intervention in high-risk clearance-limited states. It evaluates aperture passing, ring threading, and real UR5e
  assembly against BC, DAgger, uncertainty-only and other risk-aware baselines. Thus RFC cannot claim safe querying,
  precision-aware intervention, or data-efficient clearance-limited IIL in general.
- **SPARR (arXiv:2602.23253, HTML full text inspected):** trains a state-based simulation policy with dense reward,
  uses its base action as input to a vision-conditioned real-world residual RL policy, bootstraps the residual from
  successful base-plus-random-residual rollouts, and retains faster successful trajectories in a demonstration buffer.
  It evaluates real two-part assembly under socket displacement and pose-estimation noise, including wrist RGB,
  proprioception, force, and torque. It therefore closes “simulation prior + real visual residual,” “successful
  trajectory buffer update,” and generic real assembly sim-to-real residual novelty. SPARR does not describe human
  corrective trajectories, fixed physically reproducible recovery candidates, reference-relative progress/deviation
  cells, or cross-round allocation of a shared correction budget. RFC's narrow allocation hypothesis remains
  distinct only under the already required controls; C1 must never be sold as an alternative to SPARR's autonomous
  RL adaptation.
- **Wang et al. (Frontiers in Robotics and AI 2022, full XML inspected):** an adaptive imitation framework for
  complex contact-rich insertion combines a hybrid trajectory/force-learning architecture, DMP-based trajectory
  adaptation, model-free RL for force-control parameters, and goal-conditioned/self-supervised imitation to address
  motion drift and bottleneck states. It explicitly targets generalizing a trajectory profile from one task instance
  to topologically similar task variations, including simulation and real hardware. This closes claims that a nominal
  trajectory, phase/DMP alignment, or recovery from deviation is by itself a new learning contribution. Its setting
  does not describe RFC's fixed safe candidate pool, cross-round common-correction allocation, or target-weighted
  held-out allocation comparison; it is a required C1/reference-recovery precedent and a relevant model-based/force
  baseline where sensing permits.
- **Wang et al. (Frontiers in Neurorobotics 2024, full XML inspected; OEC-IRRL):** learns an
  object-embodiment-centric representation from a single teleoperated demonstration, extracts a bottleneck via-point
  from velocity change, transforms assembly via-points into the object frame, uses piecewise movement primitives for
  free-space transfer, and activates a vision/object-pose-guided residual RL policy only in the assembly phase.
  It reports fixture-less/semi-structured assembly under variable object locations with limited interaction. This is
  a direct precedent for object/reference-relative trajectory representation, bottleneck/phase segmentation, one-shot
  demonstration adaptation, and selective residual learning near assembly. It does not formulate a fixed safe
  candidate pool, use human corrective trajectories as a common budget, or compare cross-round allocation policies on
  a frozen target-weighted recovery distribution. RFC must therefore make only that allocation claim; C1 is
  infrastructure, not a paper contribution.
- **Runtime-monitoring and hybrid-control precedents (official arXiv abstracts checked 2026-08-13):** Model-Based
  Runtime Monitoring with Interactive Imitation Learning (arXiv:2310.17552) forecasts failures/OOD states to reduce
  supervision; Interactive and Hybrid Imitation Learning (NeurIPS 2025, arXiv:2412.07057) studies state-wise
  interactive annotation mixed with offline data; ARCH (CoRL 2025, arXiv:2409.16451) selects model-based/RL
  assembly primitives with a learned hierarchy; ROMAN is a Nature Machine Intelligence 2023 hybrid hierarchy.
  Therefore a planner-versus-learned map cannot be offered as a new switching architecture. At most, a separately
  validated *evaluation-induced controller-decision regret* result may support the systems path.
- **Offline active-query precedents (official arXiv abstracts checked 2026-08-13):** CRSAIL (arXiv:2512.00453)
  selects a subset of visited learner states for post-rollout expert query using expert-dataset representation/novelty
  and conformal query-rate calibration; RND-DAgger (ICLR 2025, arXiv:2411.01894) uses state OOD to trigger
  interventions. These close claims that offline selection, coverage/novelty scoring, or fewer queries per se are
  RFC's novelty. RFC must restrict itself to predeclared reference-relative finite-pool allocation and demonstrate
  target-weighted held-out recovery value beyond matched non-reference novelty/coverage selection.

The surviving hypothesis is deliberately narrower: use a *geometric nominal reference as the shared coordinate
system for recoverability-labelled, cross-round budget allocation*. It survives only if RFC outperforms failure-only
DAgger **and** DPIIL-style online risk querying under a matched correction budget. Even then, its novelty is
empirical/algorithmic rather than a new universal theory of imitation learning.

### 4.5 What this paper must not claim

- “First reference-plus-residual insertion policy,” “object/reference-frame task representation,” “bottleneck/phase
  segmentation,” “simulation base plus visual residual,” “first recovery from insertion drift,” or “success-buffered
  real assembly adaptation”: residual RL, residual assembly literature, OEC-IRRL and SPARR preclude these.
- “First safe human-query policy for precision insertion”: DPIIL precludes this.
- “First phase-aware contact recovery”: PhaForce precludes this.
- “General assembly policy”: AutoMate and PhaForce are stronger competitors, and our task family is intentionally
  narrower.
- “Model-free solution to contact”: our principal advantage is using a validated geometric reference and auditable
  data protocol, not avoiding models.

### 4.6 Explicitly not the primary line

Güleçyüz RA-L 2025, SUBTA, Adaptor, SAPS, and MPC blending are shared-autonomy/assistance references. If this paper
does not introduce real-time arbitration, intention estimation, or VLA blending as a measured method component, they
should not drive the paper title or central claim. Güleçyüz remains a relevant baseline only for any retained
confidence/arbitration ablation.

## 5. Method Skeleton

### 5.1 Inputs and reference

For task \(\tau\), the planner produces \(\xi^{ref}_{0:T}\) with phase \(z_t\), reference pose/action
\((x_t^{ref}, u_t^{ref})\), and feasibility certificate \(g_t\) (joint-limit, collision and singularity margins where
available). The observation \(o_t\) includes RGB/RGB-D, robot state, and valid previous observation/state.

### 5.2 Residual policy

\[
\Delta u_t \sim \pi_\theta(\Delta u \,|\, o_{t-k:t}, x_t, x_t^{ref}, u_t^{ref}, z_t),
\qquad
u_t^{raw}=u_t^{ref}+s_t\Delta u_t.
\]

`z_t` is reference progress supplied by the nominal trajectory for alignment and coverage accounting; it is not a
learned contact-phase controller. `s_t` is a bounded safety-dependent residual scale, not a claimed probability or
intent factor. Start with residual behavior cloning. A diffusion residual model is an ablation/model choice, not a
contribution by itself.

### 5.3 Safety projection and abstention

\[
u_t^{exec}=\Pi_{\mathcal U_{safe}(x_t,g_t)}(u_t^{raw}).
\]

The projection enforces command bounds and available kinematic constraints. If reference feasibility, observability,
or proposal validity fails, the action is `abstain/retreat/reobserve/intervene`, not a forced residual. Safety code is
not presented as a formal contact-force guarantee unless force sensing/modeling is actually added.

### 5.4 Corrective aggregation and evidence tiers

The collection mechanism is identical at the abstract level but its evidence must not be conflated.

1. Initialize with nominal demonstrations and a disclosed correction source.
2. Roll out the current residual policy within the shared safety gate.
3. Detect failures/boundary states through task outcome, safety projection, recovery failure, low validity, or coverage gaps.
4. Query the source from the live state, preserve the triggering state, and aggregate by episode.
5. Retrain with the pre-registered budget/seed protocol.

**Simulation pilot:** the source is the common deterministic local geometric/MPC oracle. The resulting data are
oracle corrections, not human demonstrations; the budget is oracle queries/corrected horizons.

**Human validation:** the source is teleoperated local correction. Only this tier may report operator time, correction
burden, or human-data efficiency. Call the procedure “DAgger-style corrective aggregation” only if it iterates on the
learned policy's own state distribution; otherwise call it “corrective demonstration collection.”

### 5.5 Candidate method: reference-aligned recovery-frontier collection (RFC)

RFC is the only candidate here intended to exceed a standard residual-BC plus DAgger composition. It uses the
reference to make correction allocation comparable across episodes rather than scoring raw trajectory smoothness.

1. **Reference alignment.** Align observations/actions to a progress-indexed local frame of \(\xi^{ref}\); derive
   normalized translational and rotational residual coordinates using task-specific clearance/tolerance constants.
2. **Recoverability labels.** After each executed rollout/query, record one of `nominal_success`, `corrected_success`,
   `failed_recovery`, `safety_abstain`, `reference_invalid`, or `unobservable`. A successful correction from the
   declared source is evidence of local recoverability: an oracle-labelled estimate in simulation and a
   human-corrected observation only in real teleoperation.
3. **Frontier estimation.** Aggregate completed outcomes by the **query-time** cell \((z,\hat\delta,v)\), while retaining
   contact/recovery labels only for audit and held-out stratification. Estimate uncertainty and sample support at the
   episode level. This is empirical calibration, not a claim of a physically exact contact trust region.
4. **Budgeted query.** Before the next collection round, select perturbation/progress cells using \(q(\psi)\), subject to
   a hard safety envelope. The shared source either supplies a local correction or the cell is marked unrecoverable
   under the declared protocol.
5. **Policy update and stopping.** Train the same residual model for RFC, random, and reactive-DAgger datasets.
   Stop at the pre-registered correction budget: oracle-query/corrected horizon in simulation or active operator time
   in a human study. Never stop one condition early because its curve is favorable.

This formulation puts the reference where it matters: not merely as an action offset, but as a coordinate system for
measuring which local failures are covered and worth asking a human to correct.

**[REVIEWER: causal availability / label leakage]** Contact state, successful recovery, and jam labels often become
known only after attempting an action or requesting the oracle. Using such a label to rank that same candidate is
oracle leakage and invalidates the allocation comparison. The implementation must save an immutable snapshot of each
`pre_query_score_inputs` before execution, then separately save `post_query_audit_labels`. With only RGB-D and
kinematics, this platform cannot claim online seated-versus-jammed classification when these states are visually
aliased; it may report them after outcome/sensor evidence or abstain. A version requiring current contact labels at
query time needs added measurable sensing and is a different method.

### 5.6 Rejected alternative: phase-aligned contact residuals (PAR)

**Status: rejected as a primary contribution on 2026-08-12.** The technical question was whether an insertion
reference should be represented as a single global action offset, or as phase-aligned local frames with different
correction semantics before contact, at contact acquisition, during constrained insertion, and during retreat/retry.
PhaForce directly covers the stronger force-aware version of this design.

Potentially meaningful distinction from generic residual control:

1. **progress is state/contact-aligned, not time-indexed:** the reference is paused, advanced, or rewound only under
   declared visual/contact transition evidence;
2. **residual coordinates are phase-specific:** lateral alignment, axial advance, orientation correction, and retreat
   are represented in a target/insertion frame, with phase-dependent allowed subspaces;
3. **recovery is a closed-loop transition policy:** rather than treating a correction trajectory as an arbitrary
   deviation from the nominal path.

**Evidence that closes this branch:** PhaForce (arXiv:2603.08342, full text inspected) introduces a contact-aware
phase predictor, slow diffusion planning, high-rate phase-routed residual correction in interpretable subspaces, and
real-robot plug-in tasks. It explicitly reports rim collisions, partial insertion, recovery/retreat-and-retry, and OOD
geometric shifts. Our current hardware stack also lacks the required wrist F/T sensing. Naming an RGB-D-only variant
with similar phase/residual language would be a weaker reproduction, not a contribution.

**Allowed residual use:** phase labels may remain dataset annotations/analysis strata, and a local frame may remain an
implementation choice. Neither is advertised in title, abstract, or contributions. A future phase-control project
would need a concrete technical difference and comparable F/T sensing; it is out of scope for this paper.

### 5.7 Data value is not a single quality scalar

Separate four records:

- recording eligibility: synchronization, missing fields, time monotonicity;
- feasibility/safety: reference validity, limits, collision/singularity proxy;
- task outcome: success, failure mode, recovery result;
- learning utility: coverage novelty, intervention state, policy error, diversity.

Smoothness contributes only as one diagnostic. A successful high-jerk recovery can have high utility; a smooth failed
episode cannot become valuable merely by passing a trajectory metric.

**[REVIEWER]** “Why not use robust planning/MPC rather than learning?”

**Required test:** include a strong model-based local-recovery or replanning baseline where feasible. State that the
learned residual is intended for model/perception/contact mismatch within \(\mathcal R_\tau\), not to replace a
planner where accurate models suffice. The MPC oracle used to standardize simulated correction labels is not M0: M0
must execute autonomously at test time, while the oracle is available only during data collection for every learning
condition.

## 6. Experimental Design Skeleton

### 6.1 Conditions

| ID | Condition | Purpose |
|---|---|---|
| A | `nominal_reference_only` | establishes how often geometry alone suffices |
| B0 | `behavior_cloning_all` | tests whether reference conditioning matters |
| B1 | `reference_residual_bc` | principal residual-policy comparison |
| B2 | `reference_residual_corrective_aggregation` | tests whether targeted recollection improves B1 |
| J0 | `JUICER_style_success_rollout_expansion` | supplementary, resource-different control: add only successful complete rollouts without new correction queries |
| A0 | `random_safe_candidate_allocation` | controls for access to the common seeded safety-valid candidate pool |
| U0 | `generic_uncertainty_coverage_allocation` | controls for ordinary active uncertainty/coverage selection on a matched non-reference partition |
| B3-no-z | `RFC_without_reference_progress` | tests whether reference progress, rather than generic reference-relative deviation bins, carries allocation value |
| B3-no-rec | `RFC_without_historical_recoverability` | keeps reference cells and coverage but removes all historical outcome-derived score terms; tests the actual recovery-frontier mechanism |
| B3 | `reference_residual_RFC` | tests reference-aligned cross-round recovery-frontier allocation |
| M0 | `reference_relocalize_replan` | strong non-learning local recovery baseline using the same observation/state estimate and safety envelope |
| W0 | `force_DMP_goal_conditioned_recovery` | supplementary Wang-et-al.-style recovery capability baseline; only fair when force sensing, DMP/goal representation and interaction resource are matched |
| I0 | `reference_residual_precision_risk_IIL` | DPIIL-style risk/precision-triggered online intervention with matched shared safety gate and human budget |
| T0 | `ThriftyDAgger_style_novelty_risk_gating` | direct budget-aware current-rollout novelty/risk intervention baseline; resource/timing accounting reported separately |
| Q0 | random equal-budget subset | data-value baseline |
| Q1 | smoothness-only subset | RINSE-style stress baseline |
| Q2 | result-aware/coverage-aware subset | candidate data-flywheel rule |

Any shared-autonomy condition is a separate experiment, not silently folded into B1.

### 6.2 Task and split protocol

- Use at least three LRI geometries: cylindrical peg, USB-C, RJ45.
- Define clearance, allowable orientation, insertion depth, and success sensing for each task before data collection.
- Generate a fixed perturbation matrix: in-domain low/medium/boundary and explicitly out-of-domain severe deviations.
- Generate visibility conditions: visible, bounded occlusion, persistent-occlusion abstention.
- Hold out combinations, not random frames. Pre-register a seed list and episode/operator/session grouping.

### 6.3 Primary tests

1. **C1:** B1 vs A and B0 on held-out perturbation/contact/visibility cells. Primary: success and recovery rate.
2. **Model-based challenge:** M0 vs A and B1. M0 re-estimates the relative target/reference transform when observations
   are valid, projects a local pose correction within the same safety envelope, replans/re-times the remaining reference
   segment, and retreats/reobserves when estimation or planning fails. It receives no human correction data. If M0 is
   competitive, narrow the learned-policy claim to errors not captured by its pose/replanning model; do not claim that
   learning is needed for all local deviations.
   Where force sensing and implementation time permit, report `W0`, a Wang-et-al.-style DMP/goal-conditioned or
   hybrid trajectory-force recovery capability baseline. `W0` is supplementary rather than a primary RFC allocation
   control because matching its force observations, DMP representation, and RL interaction budget changes the
   observation/resource setting. If `W0` is omitted, state the missing sensing and do not call that omission evidence
   that RFC is superior to force-aware insertion learning.
3. **C2:** Q2 vs Q0/Q1 at equal correction budget and identical training protocol. Primary: held-out success/recovery;
   report retained successful-recovery fraction.
4. **Aggregation:** B2 vs B1 after equal additional operator time. Measure policy-state coverage and recovery gain.
5. **RFC test:** B3 vs A0, B2, I0, T0, U0, B3-no-z and B3-no-rec at equal initial data, collection time, correction time, rollout
   count, safety envelope, perturbation generator, and training seeds. Primary: held-out recovery success per matched
   oracle query/corrected horizon in simulation, then per active operator minute in the human replication;
   secondary: recovery-cell coverage, abstention correctness, and performance near/just outside the empirical frontier.
   `J0` is reported separately: it controls for JUICER-style success-only rollout expansion, but consumes a different
   resource (additional environment rollouts rather than matched correction queries) and must not be inserted into the
   common-oracle primary estimand without a separately matched interaction/data-volume protocol.
6. **Sim-to-real:** pre-register a small real subset after matching action/observation semantics; report both agreement and
   mismatch, not only best runs.

### 6.3a Fallback systems/evaluation test: planner-versus-learned capability map

This test becomes primary only if RFC fails its pre-committed gate. It is not a post-hoc rescue: experiment `E6` must
use the same reference-relative coordinate and a frozen grid of progress, normalized translation/rotation deviation,
observability/validity, and post-query audit strata. For every held-out cell, evaluate:

- `A`: nominal-reference execution;
- `M0`: relocalize target/reference, locally replan/re-time, then retreat/reobserve when invalid;
- `B1`: reference-conditioned residual recovery behind the same safety constraints;
- `abstain`: no forced insertion when validity/safety is rejected.

The output is a capability map with four non-interchangeable labels: `M0_sufficient`, `B1_adds_value`,
`both_fail_or_abstain`, and `undetermined`. `B1_adds_value` requires a predeclared effect threshold and uncertainty
support against M0, not merely a higher average. `M0_sufficient` is a positive result, not an embarrassment: it
prevents claiming learning is needed where geometric relocalization solves the error. The map is useful only if it
changes a declared controller-selection/abstention rule on held-out cells. IID episode scores, smoothness filtering,
and unstratified aggregate success are secondary and may not replace cellwise all-attempt outcomes.

**[REVIEWER: hidden switching-policy concern]** `E6` is an evaluation and deployment-diagnostic protocol, not a
learned mixture-of-experts or a new arbitration controller. The map may inform a manually predeclared deployment
recommendation only after the comparison. If the project trains a predictor that selects M0 versus B1 online, that is
a new method requiring its own train/test split, calibration, switching baselines, and safety analysis; it may not be
quietly reported as a consequence of the capability-map experiment.

**[REVIEWER UPDATE: E6 is not presently a fallback contribution.]** The direct literature check strengthens this
restriction. Runtime-monitoring IIL already learns to forecast high-risk/OOD execution and request intervention
(Liu et al., arXiv:2310.17552). Hybrid IL has explicit theory for mixing offline demonstrations with state-wise
interactive annotation (Li and Zhang, NeurIPS 2025, arXiv:2412.07057). In contact-rich assembly, ARCH (CoRL 2025,
arXiv:2409.16451) already uses a high-level learned policy to select parameterized model-based and learned
primitives. ROMAN is an additional hierarchical hybrid-control precedent. These sources do not, from their verified
abstracts, establish the exact LRI reference-cell evaluation grid. They do establish that an E6 heatmap, a
planner-versus-policy selector, or a claim that hybrid selection is itself new is insufficient.

**Revised status.** If RFC fails, retain E6 first as an *internal negative-result and deployment diagnostic*, not a
submission thesis. It can be promoted only if the paper states and validates a distinct measurement claim: a
predeclared reference-relative, recovery-cell risk estimate changes the choice between named controllers on a
frozen target distribution, while conventional aggregate/IID evaluation gives a different and worse choice.
Promotion additionally requires a released, reconstructible cell definition, a decision loss/cost matrix agreed
before test labels are seen, and a held-out decision-regret comparison against the aggregate-score choice. Without
that decision-regret result, E6 is experimental hygiene, not a contribution. It must never be reframed as a learned
runtime monitor or hybrid selector without a separately scoped method paper.

### 6.4 Metrics and statistics

- Primary: task success, recovery success.
- Safety: abort/retreat correctness, constraint violation, contact force only if measured.
- Efficiency: correction time, human interventions, data budget, training steps.
- Control diagnostics: command-state error, jerk, reference deviation.
- Calibration only if C3 is run: ECE and risk-coverage.
- Statistics: episode-level grouped bootstrap CI; mixed-effect/paired analysis if multiple operators; no frame-level p-values.

### 6.5 RFC fairness and falsification protocol

RFC can appear superior through unequal exposure, unsafe probing, or extra human time rather than better allocation.
The following controls are therefore mandatory for its primary comparison.

| Confound | Required control | Falsification consequence |
|---|---|---|
| More correction resource | In simulation, match oracle queries and corrected horizons; in human studies, match initial demonstrations, number of rounds, total operator correction seconds, and reset/setup time. Report both wall-clock and active correction time. | An RFC gain without the appropriate matched budget is descriptive only. |
| Easier/harder encountered failures | Use the same seeded perturbation candidate pool and the same safe envelope for all conditions. Selection may reorder/query cells but cannot expand its allowed envelope. | A gain caused by a different perturbation pool does not support C2. |
| Evaluation on selected candidates | Freeze a disjoint, seeded and stratified held-out target distribution before collection; evaluate every condition there, not on its adaptively selected candidates. Report selected-pool outcomes only as process diagnostics. | Success measured only on selected cells is selection bias, not recovery generalization. |
| Natural deployment distribution | If collected, run a separate uncontrolled/natural rollout protocol and report it without claiming it was optimized by RFC. | Fixed-pool target success does not identify natural-failure-distribution performance. |
| Different online intervention rule | Run every learning condition behind the same safety gate; for the RFC-vs-I0 contrast, make the online gate identical and vary only the *next-round allocation* of correction opportunities. | A gain caused by more timely safety handovers supports neither RFC nor cross-round allocation. |
| Budget-aware gating locus | Run T0 with its disclosed novelty/risk engagement rule, but match common oracle queries and corrected horizons; report trigger count, online intervention horizon, candidate-pool exposure and timing separately. | A comparison that only matches nominal “interventions” while allowing different corrected horizon or exposure is not an allocation result. |
| More raw data or training | Match accepted episode count, frames/action horizon where relevant, training steps, model architecture, and random seeds. Retain discarded data only for audit, not training. | A gain from more optimization/data is not allocation efficiency. |
| One favorable candidate/model seed | Use independent outer collection trials. Within every trial share initial data, candidate pool, validation/target assets and paired optimizer seeds across methods; analyze paired trial-level differences. | Episode bootstrap from a single trained policy is insufficient evidence for a collection-rule effect. |
| Target-set tuning | Freeze a validation distribution distinct from collection and final target; tune score weights/cell boundaries/hyperparameters only there and record amendments. | Any target-informed tuning makes the result exploratory. |
| Hidden data-volume difference | Log candidate exposure, attempts, correction horizon, accepted episodes, unique/duplicated frames, training updates and oracle calls. Report fixed-budget all-attempt and separately labelled fixed-frame analyses. | Matched nominal queries alone cannot isolate allocation from data volume. |
| Success-rollout expansion | Report JUICER-style `J0` separately with its rollout count, successful-rollout fraction, generated frames, and environment interactions. Do not compare it as equal correction budget unless all non-oracle resources are also matched. | An apparent RFC gain/loss against an unmatched success-rollout expansion does not isolate allocation. |
| Oracle knowledge at query time | RFC may use only data available before the shared correction source responds to the queried state. Post-correction outcome updates the next round only. | Any use of future success labels invalidates the online collection claim. |
| Selective safety aborts | Count safety abstentions, rejected cells, and all attempted queries in the denominator; separately report success conditional on non-abstention. | Hiding difficult states through abstention invalidates recovery claims. |
| Operator learning/order effect | Counterbalance method order across operators/sessions; reserve disjoint test episodes and report per-operator results. | A single-operator late-session gain is exploratory only. |

The primary estimand is the episode-level difference in held-out recovery success at a fixed correction budget:
\[
\Delta_{RFC}=\Pr(\mathrm{recover}\mid B3,\mathcal T_{holdout},B_{corr})-
\max\{\Pr(\mathrm{recover}\mid A0,\mathcal T_{holdout},B_{corr}),
\Pr(\mathrm{recover}\mid B2,\mathcal T_{holdout},B_{corr}),
\Pr(\mathrm{recover}\mid I0,\mathcal T_{holdout},B_{corr}),
\Pr(\mathrm{recover}\mid T0,\mathcal T_{holdout},B_{corr}),
\Pr(\mathrm{recover}\mid U0,\mathcal T_{holdout},B_{corr}),
\Pr(\mathrm{recover}\mid B3\text{-no-}z,\mathcal T_{holdout},B_{corr}),
\Pr(\mathrm{recover}\mid B3\text{-no-rec},\mathcal T_{holdout},B_{corr})\}.
\]
When `C0` is run, include it in the maximum as a required broad-active-query comparator. The reported primary
quantity is the predeclared target-weighted version of this estimand, with cell weights \(w_c\); unweighted success
is secondary. Weights, cell boundaries, and the target distribution must be saved before any adaptive allocation
round. Otherwise a method may manufacture a favorable average by allocating and evaluating mostly easy or mostly
common cells.
The `B3-no-z` contrast is separately necessary for a reference-progress-specific statement. A non-significant or
negative contrast does not invalidate reference-relative allocation as an empirical heuristic, but it removes the
progress-specific part of the contribution. The `B3-no-rec` contrast is separately necessary for “recovery
frontier” or “recoverability-aware” wording: if it is null or negative, historical outcomes did not add value beyond
reference-stratified coverage and that wording must be removed.
Report a grouped bootstrap confidence interval over test episodes, preserving episode/session/operator grouping. The
secondary efficiency curve is recovery success against cumulative oracle queries/corrected horizons in simulation and
against active correction minutes in human studies. Comparison at one budget must be declared before collection. Do
not choose the best point after seeing the curve.

### 6.5a Target-distribution preregistration options

The target weights \(w_c\) are part of the scientific question, not a reporting detail. Choose exactly one primary
scheme before candidate generation; publish the seed and cell counts. A second scheme may be reported only as a
clearly labelled sensitivity analysis.

| Scheme | Definition | What it supports | Main reviewer objection | Recommendation |
|---|---|---|---|---|
| `uniform-cell` | Equal weight over all safety-valid, physically reproducible LRI cells. | A controlled claim about recovery coverage across the declared envelope. | Not a natural deployment distribution. | Recommended for the RFC viability pilot: reproducible and least susceptible to post-hoc frequency choices. |
| `fixture-prior` | Weights fixed from a documented task/fixture perturbation protocol measured before collection. | A claim about that measured engineered deployment prior. | The fixture prior may not match real uncontrolled failures. | Recommended only after the first physical setup has repeatability data. |
| `natural-prior` | Weights estimated from a separately frozen, uncontrolled rollout log. | A descriptive claim about that observed deployment mixture. | Selection/measurement bias; rare safety-critical cells may vanish. | Exploratory unless logging and sampling are frozen before method development. |

**[OPEN: target-distribution decision required before E5.]** For the simulation viability pilot, shall the team
freeze `uniform-cell` as primary and reserve `fixture-prior` only for later real replication? This is the current
recommendation. It does not claim natural-frequency optimality, but cleanly tests whether RFC improves the stated
recovery envelope rather than a post-hoc selected failure mixture.

**[REVIEWER]** “Your recovery frontier is estimated from human success, so it is only an operator-skill map.”

**Required response:** agree with the limitation, then test cross-operator transfer and report operator-conditioned
frontiers. The primary claim is allocation for the declared interface/operator distribution, not a hardware-invariant
physical recoverability set. A cross-operator claim requires a held-out-operator experiment.

**[KILL: RFC]** If B3 does not exceed A0, reactive DAgger (B2), DPIIL-style precision/risk IIL (I0),
ThriftyDAgger-style budget-aware gating (T0), and generic uncertainty/coverage allocation (U0), with the same safety
gate and correction budget, RFC is not an algorithmic contribution. If it does not exceed B3-no-z, remove any
reference-progress-specific claim. If it does not exceed B3-no-rec, remove “recovery-frontier” and
“recoverability-aware” wording: the result supports at most reference-stratified coverage. Retain labels and
coverage analysis only as experimental diagnostics; remove unsupported RFC language from the title, abstract, and
contribution list.

### 6.6 RFC viability pilot: pre-commit gate

This pilot is deliberately small and simulation-only. Its purpose is to decide research direction, not to report final
results.

| Element | Fixed pilot specification | Reason |
|---|---|---|
| task | one peg or USB-like insertion with known nominal geometry | isolates allocation from cross-task generalization |
| reference | one validated collision-free geometric reference and one reference frame convention | prevents planning variance from becoming a method difference |
| conditions | A0 random safe-candidate allocation, B2 reactive DAgger, I0 DPIIL-style risk query, T0 ThriftyDAgger-style novelty/risk gate, U0 matched generic uncertainty/coverage allocation, B3-no-z progress ablation, B3-no-rec history-free coverage ablation, B3 RFC; `C0` CRSAIL-style post-rollout representation novelty if broad active-query wording is retained; optional `W0` Wang-et-al.-style force/DMP recovery when sensing is matched; J0 reported separately | distinguishes allocation from candidate-pool access, current-rollout gating, generic active selection, reference-free binning, historical-outcome value, post-rollout representation novelty, force-aware recovery capability, and resource-different success-rollout expansion |
| safety | one shared state/constraint gate and the same retreat/reset behavior | RFC may not win by avoiding different states |
| correction oracle | one deterministic local geometric/MPC expert called from the perturbed state; identical controller, action limits, horizon, and reset behavior for A0/B2/I0/T0/U0/B3-no-z/B3-no-rec/B3 | replayed demonstrations are invalid after state perturbation; the pilot measures allocation, not human skill |
| budget | predeclare one oracle-query plus corrected-horizon budget, rollout count, and setup/reset accounting | makes simulation allocation efficiency meaningful without falsely reporting human time |
| data/model | matched initial data, accepted frame count, policy architecture, optimizer, steps, and seeds | prevents a training-compute explanation |
| test | disjoint, seeded held-out target distribution; primary evaluation never reuses adaptively selected candidate opportunities; no frame-level split | measures declared recovery-target generalization rather than selected-pool success |
| decision | paired outer-trial CI for B3 against A0/B2/I0/T0/U0 at the declared budget; B3-no-z for progress-specific wording; B3-no-rec for recovery-frontier wording; `C0` when broad active-query wording is retained | prevents post-hoc curve selection and generic-gating explanations |

**Pilot stop rule.** RFC proceeds as an algorithmic candidate only if it beats A0, B2, I0, T0, and U0 on the disjoint
held-out target distribution per matched oracle-query/corrected horizon, with bootstrap support and without a worse
all-attempt safety/abstention result. It may claim reference-progress-specific value only if it also beats B3-no-z,
and recovery-frontier/recoverability-aware value only if it also beats B3-no-rec.
Any claim beyond the declared LRI allocation family additionally requires a matched `C0` representation-novelty
control. Otherwise, do not use generic active-query or query-efficiency language.
Otherwise freeze RFC as a diagnostic and switch the paper's primary question to reference-anchored recovery
evaluation. Winning only against B2/I0 is insufficient: it can be explained by ordinary active selection or
budget-aware current-rollout gating.

**Simulation-to-human evidence ladder.** (1) The pilot may establish only that RFC allocates a common *oracle* more
effectively. (2) A subsequent real-teleoperation experiment must match active operator time and show the same ranking
before claiming human-data efficiency. (3) Simulation and human results that disagree are a negative sim-to-real
finding, not evidence to select the favorable result.

**[REVIEWER: candidate-space transfer]** A simulator can reset to arbitrary seeded perturbation cells. A real
teleoperator cannot necessarily reproduce, safely reach, or repeatedly initialize the same contact state. Therefore
the human replication is not “run RFC on the same cells”: it is a separate, pre-registered experiment over a
**physically reproducible candidate pool**. Each candidate must be defined by a fixture-indexed target offset, a
validated pre-contact robot waypoint plus controlled offset, or an externally measured object pose perturbation;
record its reset procedure, measured initial state, acceptance tolerance, repeatability estimate, safety precheck,
and pre-query features. Match active correction seconds *and* reset/setup/abort time. Do not select accidental,
unrepeatable contact states as if they were pool elements, and do not rank real candidates using simulator-only
contact labels. Thus a positive pilot establishes common-oracle allocation only; a matched human replication is
required to establish allocation of human corrective effort. The executable contract is in
`config/rfc_viability_pilot.yaml` under `human_replication_contract`.

**[DECISION RECORDED FOR PILOT]** Use a deterministic local geometric/MPC correction oracle, not replayed
teleoperation. It must start from the perturbed live state and be identical across B2/I0/B3. The pilot must never call
its output human demonstration data.

**Executable preregistration:** [RFC viability pilot configuration](config/rfc_viability_pilot.yaml) freezes the
shared oracle, condition definitions, state cell, immutable audit fields, metric, bootstrap grouping, and stop rule.
The experiment registry entry is `E5`; the revised claim registry entry is `C2`. Any implementation that changes
these without a dated amendment is exploratory rather than confirmatory.

**[OPEN: pilot geometry]** The configuration recommends a cylindrical peg-in-hole as the initial viability task. It
isolates reference-relative perturbation and budget allocation; a USB-like connector would better match the eventual
application narrative but introduces asymmetric contact, visually ambiguous jam/seated states, and unmeasured force
as confounds. A peg result cannot establish connector generalization. A USB-only negative result cannot falsify RFC
cleanly on the current RGB-D/kinematic stack. Freeze this choice before implementation.

### 6.7 Evidence table required before submission

| Claim | Minimum evidence | Kill condition |
|---|---|---|
| C1 residual recovery | B1 wins over A and B0 on held-out LRI cells without safety tradeoff | no gain or only gains on training-like cells |
| E6 capability map fallback | Not a contribution by default. Promotion requires predeclared controller-action costs and held-out evidence that an LRI-cell risk estimate has lower controller-decision regret than an aggregate/IID decision rule. | a heatmap only; small aggregate differences; no lower-cost decision; hidden learned switching policy |
| C2 fixed-pool allocation value | B3/RFC improves target-weighted recovery on the disjoint held-out target distribution per matched oracle query/corrected horizon over A0, B2/reactive DAgger, I0/DPIIL-style risk IIL, T0/ThriftyDAgger-style gating, and U0; `C0`/CRSAIL-style novelty is required for broad active-query wording; human-time efficiency is claimed only after physical-pool replication | any matched baseline is equal or better; gain is selected-pool-only or explained by different safety gating, exposure, candidate construction, future-label leakage, or untested generic post-rollout novelty |
| C3 validity calibration | lower risk at comparable coverage after calibration | confidence cannot predict failures |
| taxonomy | at least three geometries and all declared axes, including OOD abstention | only one axis/task evaluated |

## 7. Anticipated Reviewer Attacks And Responses

| Attack | Why credible | Required evidence or revision |
|---|---|---|
| “Known geometry means planning solves it.” | Old review W2; Wang et al. 2022/2024 use goal-conditioned or object-frame/bottleneck recovery and hybrid force/residual learning for contact-rich insertion | demonstrate failures within calibrated but perturbed/contact-mismatched settings; compare strong planner/local recovery and relevant goal-conditioned/model-based baselines |
| “Why not just relocalize and replan?” | target geometry/reference are known | include M0 with the same sensing, constraints and retreat policy; identify the failure cells where residual learning adds value |
| “Residual BC is trivial / why not use SPARR or adaptive insertion IL?” | residual/hybrid assembly critique; SPARR and Wang et al. cover visual residual adaptation, one-shot object-frame bottleneck representations, DMP/goal-conditioned recovery, and force-learning variants | treat B1 as capability infrastructure, not a contribution; state the distinction in correction source, fixed candidate pool, reference-relative allocation **for data allocation**, and target-weighted held-out evaluation; any RFC claim must survive B2/I0/T0/U0 and, if broad, C0 under the shared gate |
| “Data quality score is hand-tuned.” | RINSE challenge | do not claim universal score; test fixed-budget downstream value and report harmful exclusions |
| “Occlusion claim is misleading.” | observability concern | test only bounded re-observable occlusion; include persistent-occlusion abstention failure category |
| “Three tasks are superficial.” | old review W3 | use geometry/contact/visibility axes and held-out combinations, not three demonstrations |
| “Real robot evidence is weak.” | sim-to-real concern | report a pre-registered real subset and all safety/semantic mismatches |
| “You changed the paper after rejection but still hide α.” | old review W1/W5/W9 | remove intent/probabilistic/α language unless a measured shared-autonomy method remains |
| “Tilde/DexCap/DPIIL/ThriftyDAgger already collect or safely query corrections.” | direct prior work, including clearance-limited RA-L 2024 DPIIL and CoRL 2021 budget-aware novelty/risk gating | do not claim online intervention novelty; show only cross-round fixed-pool allocation after matching the shared gate and current-rollout gating control |
| “CTR already defines local contact control.” | direct theory prior | cite it, do not claim CTR; show our contribution is learning/data collection under an empirical recovery boundary |
| “Your simulator oracle bakes in the answer.” | collection oracle and autonomous baseline can be conflated | disclose the oracle, use it identically for B2/I0/B3, hold it out from M0 test-time execution, and replicate ranking with human teleoperation before human-efficiency claims |

## 8. Conclusion Skeleton

We frame precision insertion as local recovery around a feasible reference rather than unrestricted assembly or human
intent inference. The proposed study first tests whether reference-conditioned residual learning improves held-out
recovery under a declared task boundary. It then tests the stronger RFC hypothesis: whether reference-aligned
cross-round fixed-pool allocation beats A0 random allocation, reactive DAgger, DPIIL-style risk querying,
ThriftyDAgger-style novelty/risk gating, and generic uncertainty/coverage selection at equal correction budget on a
disjoint held-out target distribution. The conclusion must separate oracle-based simulation evidence from matched
human-time evidence, report where the method fails, and state whether simulation findings survive the pre-registered
real subset. If RFC does not pass its equal-budget test, the conclusion must explicitly present it as a
negative/exploratory collection result rather than silently retaining it as a contribution.

## 9. Limitations Draft

1. The recovery region is empirically estimated, not a formal robust-contact guarantee.
2. Known target geometry and a nominal reference are required; global perception/planning is outside scope.
3. Bounded re-observable occlusion is not persistent blind insertion.
4. Early experiments cover limited connector geometries, robot hardware, operators, and contact-force sensing.
5. Corrective aggregation may be operator- and interface-dependent; cross-operator claims require dedicated splits.
6. Offline trajectory metrics diagnose quality but do not replace outcome labels or safety certification.
7. The initial RFC pilot uses a deterministic local geometric/MPC oracle, so it cannot establish human demonstration
   efficiency, human correction quality, or operator transfer.
8. This work does not compete with force/torque-driven phase-control systems such as PhaForce; our platform's RGB-D
   and kinematic sensing cannot distinguish visually identical seated and jammed contact states at the same level.
9. RFC is evaluated on a declared, safety-valid, physically reproducible candidate pool and a separate held-out target
   distribution. Its result does not identify or optimize the uncontrolled natural distribution of deployment failures;
   any such rollout test is separately reported and cannot be inferred from fixed-pool performance.

## 10. Open Decisions For Team Discussion

1. **[DECISION REQUIRED]** Does the RFC viability pilot earn an algorithm-paper path, or does the project switch to
   the evaluation/systems path? Do not decide this before the pre-committed B2/I0/B3 result.
2. **[DECISION REQUIRED]** What measurement supplies success and contact/jam labels for USB-C and RJ45? A visual
   endpoint alone may be insufficient.
3. **[DECISION REQUIRED]** What is the operational definition and calibration protocol for \(\mathcal R_\tau\)?
   Candidate: success of a fixed recovery controller/human correction within horizon and safety bounds.
4. **[DECISION REQUIRED]** Can we implement a credible model-based local-recovery baseline? Without it, reviewers may
   say residual learning only compensates for an intentionally weak planner.
5. **[DECISION REQUIRED]** Is a wrist camera part of the final observation model or only a data-collection aid? Freeze
   this before collecting confirmatory data.
6. **[DECISION REQUIRED]** Which contribution is mandatory after the pilot? C1 is a required capability result; C2
   is dropped from title/contribution list if its matched-budget gains do not materialize; C3 is explicitly optional.
7. **[DECISION REQUIRED]** Does the RFC query score use only pre-query \((z,\hat\delta,v,h)\) information, with
   contact/jam outcomes available only after execution? This is now the leakage-free default. If the team instead
   needs real-time contact-mode input, identify an actual measurable sensor/estimator and treat it as a new sensing
   requirement and a different method; RGB-D/kinematics alone cannot justify it for visually aliased jam/seated states.
8. **[DECISION REQUIRED BEFORE REAL RFC REPLICATION]** Which repeatable physical candidate-pool mechanism is available
   for the first peg task: a fixture with indexed target offsets, robot reset to a validated pre-contact waypoint plus
   controlled offset, or externally measured target perturbations? Do not make a human-time/data-efficiency claim
   until one is measured for reset repeatability and safety. The simulation seed pool is not a substitute.
9. **[DECISION REQUIRED: theory versus empirical method]** Do we invest in a formal active-design/bandit-style RFC
   objective with stated assumptions and a proof target, or explicitly submit RFC as an empirically validated,
   finite-candidate allocation rule? The latter is the current honest position and does not invoke manifold,
   low-dimensional, regret, or optimality claims. Do not promise a theorem without a formal stochastic model and a
   meaningful proof that survives the safety and partial-observation constraints.
10. **[RESOLVED LITERATURE CHECK; EXPERIMENT DECISION REMAINS]** JUICER full HTML was inspected. Its verified
    backward augmentation and success-rollout `Collect-and-Infer` mechanisms do not implement the fixed-candidate,
    corrective cross-round allocation hypothesized for RFC. The remaining decision is whether to run the disclosed,
    resource-different `J0` supplementary control, or explicitly bound RFC to common-oracle correction allocation.
    Neither result authorizes broad data-efficiency, bottleneck-correction, or augmentation novelty language.
11. **[RESOLVED LITERATURE CHECK; EXPERIMENT DECISION REMAINS]** IntervenGen full HTML was inspected. It synthesizes
    object-pose-transformed, open-loop replayed human recovery segments after closed-loop policy mistake generation;
    it is not a fixed-candidate allocation method. Choose whether to implement this resource-different generator under
    a separately matched interaction/generation protocol, or explicitly exclude generative intervention comparisons
    and limit RFC to selecting real correction opportunities. Do not call I-Gen success-only output filtering unsafe or
    invalid: its objective is synthetic training-data generation, not recovery-frontier estimation.
12. **[NEW REQUIRED BASELINE]** ThriftyDAgger has official CoRL 2021 Oral metadata and abstract verification. Add T0
    as a direct novelty/risk budget-aware current-rollout gating baseline before any RFC result is called stronger than
    budget-aware interactive IL. Match common correction-source queries/corrected horizons and separately report T0
    trigger count and engagement horizon; it cannot be treated as a mere generic uncertainty allocator.
13. **[DECISION REQUIRED: target distribution]** Freeze the E5 held-out target distribution before collection and
    keep it disjoint from all adaptive collection candidates. Is the primary deployment statement restricted to this
    engineered, safety-valid recovery distribution, or will the team additionally collect an uncontrolled/natural
    rollout test? The latter is useful but exploratory unless its sampling protocol is also frozen. Do not infer
    natural failure-distribution performance from selected-candidate results.
14. **[FALLBACK DECISION REQUIRED]** If RFC fails, do we invest in a stronger `E6` *evaluation-induced decision
    regret* study, or end the algorithm-paper path? The weak form -- a planner-versus-policy heatmap -- is now
    classified as an internal diagnostic because runtime monitoring, hybrid IL, ARCH, and ROMAN cover the broader
    controller-selection space. Promotion requires a frozen cell grid, a practical cost matrix for M0/B1/abstain,
    a predeclared aggregate/IID decision rule, and held-out evidence that the LRI-cell estimate selects a lower-cost
    controller action. Do not present an after-the-fact capability map as a contribution.
15. **[DECISION REQUIRED: RFC scope versus baseline cost]** Do we accept RFC as a narrow, pre-registered
    reference-relative stratified allocation study and implement a CRSAIL-style post-rollout representation-novelty
    baseline in addition to `U0`, or limit the paper to comparison within the LRI allocation family? The first is
    substantially stronger but costs another baseline; the second forbids any broad “query efficient active IL”
    language. Neither choice permits calling \(q\) an optimal utility, a bandit rule, or a manifold method without
    new formal assumptions and proof.
16. **[DECISION REQUIRED: force-aware baseline]** Is force/torque sensing and a matched DMP/goal-conditioned
    implementation available for a supplementary `W0` baseline? If not, document the observation mismatch and retain
    Wang et al. as a limitation/related-work boundary. Do not claim RGB-D/kinematic RFC superiority over a method that
    receives force evidence we do not provide.
17. **[DECISION REQUIRED: causal replication budget]** Does the team accept paired independent outer collection
    trials as mandatory for a confirmatory RFC claim? The required number must be chosen from a pilot variance/effect
    estimate and a predeclared precision or power target, not stopped when one seed looks favorable. If compute only
    permits one candidate pool or one trained-policy seed, the RFC result is exploratory and cannot support a causal
    allocation-method conclusion.
18. **[DECISION REQUIRED: frontier-ablation cost]** Does the team accept `B3-no-rec` as a required primary condition?
    It holds reference cells, target weights, coverage, safety gate, candidate pool, budget and tie-breaking fixed,
    then removes all historical outcome terms. Without it, retain at most “reference-stratified coverage allocation”
    and remove “recovery frontier” / “recoverability-aware” from the contribution, title and abstract.

## 11. Evidence Ledger

| ID | Status | Use |
|---|---|---|
| Ross et al., DAgger, 2011 | venue/pages corroborated by Crossref-indexed later reference; original source/PDF still to archive | corrective aggregation foundation |
| Johannink et al., Residual RL, ICRA 2019 | Crossref verified: DOI 10.1109/ICRA.2019.8794127, pp. 6023-6029 | residual-control foundation |
| Suh et al., CTR, IJRR 2026 | local PDF + OpenAlex DOI; full-text read pending | local trusted-region boundary logic |
| Tilde, 2024 | local PDF; venue verification pending | interactive correction precedent |
| DexCap, 2024 | local PDF; venue verification pending | multimodal collection precedent |
| AutoMate, RSS 2024 | DOI verified earlier; full-text read pending | assembly-generalization novelty threat |
| Güleçyüz, RA-L 2025 | verified | shared-autonomy baseline, not central method unless retained |
| RINSE, 2026 | local PDF; preprint | data-quality counterargument |
| Tilde, 2024 | local PDF text inspected | direct DAgger/failure-correction novelty threat |
| DexCap, 2024 | local PDF text inspected | direct residual correction / correction-data novelty threat |
| JUICER, IROS 2024, arXiv:2404.03729 | arXiv HTML methods inspected | augmentation and successful-rollout expansion threat; fixed-pool correction allocation not found in inspected method |
| IntervenGen, arXiv:2405.01472 | arXiv HTML methods inspected | transformed/replayed synthetic intervention generation threat; not a fixed-pool allocator |
| ThriftyDAgger, CoRL 2021 Oral, arXiv:2109.08273 | official arXiv abstract verified | budget-aware novelty/risk current-rollout gating threat; T0 required |
| SPARR, arXiv:2602.23253 | arXiv HTML full text inspected; preprint | direct sim-base plus real vision-residual assembly and success-buffer-update precedent; does not establish human correction or fixed-pool reference-cell allocation |
| Oh and Matsubara, DPIIL, RA-L 2024 | full text inspected | direct safe interactive imitation-learning baseline |
| PhaForce, arXiv:2603.08342 | arXiv HTML full text inspected; preprint | closes phase-aware slow/fast residual-control branch |
| Wang et al., OEC-IRRL, Frontiers in Neurorobotics 2024 | full XML inspected | single-teleop object-frame via-points, bottleneck segmentation, phase-selective residual RL assembly precedent; does not establish fixed-pool correction allocation |
| Wang et al., adaptive contact-rich insertion IL, Frontiers 2022 | full XML inspected | DMP/goal-conditioned deviation recovery and hybrid trajectory-force insertion precedent; does not establish fixed-pool correction allocation |
