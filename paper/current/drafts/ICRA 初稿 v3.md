## Abstract
真实机器人数据的瓶颈不仅在于数量，也在于示教轨迹是否有效、可审计并且对下游策略有用。对于需要局部对准、微调或短程执行的视觉可观测任务，高质量专家数据同时包含平滑的一次性完成轨迹，以及在困难状态下稀疏、及时的局部纠正，但新手采集员往往会需要长时间尝试才能获得少量可用示教。本文提出一种面向遥操作数据采集的连续自适应视觉条件化动作滤波与辅助方法，构建并验证了数据采集闭环。系统以同构遥操作接口同步记录原始命令、机器人状态和多视角图像，将成功名义片段与人工标记的纠正区间组织为互补监督，并使用冻结的视觉编码器和离线视觉语言模型辅助任务阶段与进度审计。一个因果 CVAE--Transformer 将专家动作分布预测与辅助增益调节分为两个输出：动作头给出局部候选修正，增益头以有界且速率受限的连续状态决定其施加幅度。该方法以有界残差和连续辅助增益对操作者输入进行调节。我们在真实机器人上评估审计与监督质量、辅助行为及其跨任务和配置泛化、单位操作者时间的合格示教产率以及下游模仿学习效用，并通过固定参考审计集和跨轮独立复核检验该闭环能否持续改进数据采集过程。
## 1. Introduction
具身策略的训练正在越来越关注示教数据的质量及其下游效用，而不仅是记录数量本身[Data Pyramid, Robot Data Curation, EgoDex, Open X-Embodiment]。仿真数据、便携式遥操作、第一视角记录和大规模真实机器人数据共同扩展了具身数据的来源[Open X-Embodiment, UMI, DROID, EgoDex, MimicGen]。然而，不同采集范式对时间同步、任务阶段、操作者介入和失败原因的记录并不统一；视觉审计和视觉奖励模型开始显式建模失败、进度、near-miss 和 partial progress [AHA, RoboReward, RoboVQA, Large Reward Models]。对于视觉可观测且动作公差有限的操作，错误对齐、停滞和反复尝试会降低示教的可复用性；数据筛选与平滑性研究也显示，轨迹性质和数据选择会影响下游模仿学习[Robot Data Curation, Diffusion Policy, ALOHA]。高质量数据并不意味着每一步都需要辅助：一次性完成轨迹保留操作者的名义行为，困难状态下的局部纠正则提供恢复行为[DAgger, Robot Learning on the Job, HIL-SERL]。

现有研究的缺口不是缺少某一个独立模块，而是缺少把“审计—辅助—再采集”连成可验证闭环的方法。遥操作系统主要解决如何采集[GELLO, Open-TeleVision, DexCap, AnyTeleop, DexUMI]；数据质量和视觉模型主要解决采集后如何筛选或打分[Robot Data Curation, AHA, RoboReward]；共享控制、残差和交互式学习主要优化部署策略或专家介入成本[Residual RL, Robot Learning on the Job, ThriftyDAgger, FlowCorrect]。这些方向尚未直接回答：在固定操作者时间和安全边界下，能否让下一轮遥操作产生更多 task-valid demonstrations，同时在正常阶段保持接近原始命令？

我们因此研究一个窄而可测的问题：学习一个视觉条件化、因果且有界的连续动作滤波器，在正常阶段保持低辅助增益，在困难阶段逐步提高辅助增益，并以合格示教产率而非干预次数作为闭环目标。

我们将纠正区间作为弱监督，而不是人为定义逐帧 residual 标签。操作者或审计员只需标记纠正开始和结束；区间内的同步轨迹提供困难状态下的局部专家行为，并鼓励较高但连续变化的辅助增益，区间外的一次性成功轨迹则提供同样重要的正向监督，约束滤波器保持低增益、少偏离原始命令。冻结的视觉编码器提供连续观测，视觉语言模型在离线阶段生成阶段、进度、停滞和恢复等带置信度的审计候选，经人工复核后用于构造训练视图和数据准入。模型学习后，专家动作预测与操作者命令之差形成有界残差，时变增益连续调节其作用幅度。执行产生下一时刻的新视觉观测，由此形成可审计的数据采集飞轮。

基于上述观察，我们先从同步轨迹中构造可审计的互补监督，再学习视觉条件化的连续辅助，最后通过固定预算的跨轮采集检验新增数据的数量与效用。我们的贡献如下：

1. 提出面向视觉可观测精细操作的 correction-aware 可审计示教表示，将纠正区间与成功名义片段组织为互补监督，并通过 $A_{\rm action}$ 与 $A_{\rm audit}$ 的分离控制动作训练的数据准入。
2. 提出视觉条件化的连续动作滤波器，分别建模候选专家动作与辅助增益，并约束增益的幅度和变化速度，使辅助能够随任务上下文连续调节。
3. 构建真实机器人的迭代采集闭环，以固定操作者预算下的合格示教产率为主要指标，并通过独立审计和下游模仿学习评估新增数据的可靠性与效用。
## 2. Related Work

### 2.1 遥操作示教与其他数据采集范式

低成本同构遥操作、主从双臂、可穿戴手部接口和视觉重定向分别降低了真机示教的硬件门槛，并扩大了可采集的 embodiment 范围[GELLO, ALOHA, Mobile ALOHA, UMI, DexCap, AnyTeleop, DexUMI]。DROID、Open X-Embodiment、EgoDex 和 MimicGen 进一步展示了跨场景真实数据、第一视角数据和示教驱动扩增的规模化路径[DROID, Open X-Embodiment, EgoDex, MimicGen]。这条路线解决了如何获得更多示教，却通常把操作者命令当作需要记录的输入，而不是采集过程中可根据任务状态连续调节的控制信号；数据契约、纠正阶段和失败原因也并非所有范式的共同接口。本文沿用这些遥操作链路，研究其上的连续动作滤波和数据质量闭环，而不是新的硬件或完整自主策略。

### 2.2 机器人示教数据质量、数据筛选与视觉审计

示教质量研究通常从信息量、覆盖度、轨迹性质或任务/模型因素出发，判断哪些离线样本更值得保留或用于训练[Robot Data Curation, RoboMimic, Diffusion Policy, ALOHA]。这类工作建立了数据质量应由下游效用验证的原则，但主要发生在采集完成之后，不能改变操作者已经花费的时间。另一条路线使用视觉或视觉语言模型判断成功/失败、阶段、进度、near-miss 或过程奖励[AHA, RoboVQA, RoboReward, Large Reward Models]；它们提供可扩展的审计信号，但仍受上下文和置信度不确定性的影响。本文将冻结视觉表征和经过人工复核的离线审计候选用于构造训练视图和数据准入，使审计结果能够影响下一轮真实采集。

### 2.3 学习型共享控制、残差策略与动作纠正

Residual Reinforcement Learning、动态 authority allocation、Robot Learning on the Job、HIL-SERL 和 FlowCorrect 说明，人类介入或基策略残差可以改善部署控制和失败恢复[Residual RL, Dynamic Authority Allocation, Robot Learning on the Job, HIL-SERL, FlowCorrect]。它们共同支持“保留已有控制能力、只在局部困难状态引入受约束修正”的原则，但主要评价任务成功率、策略适应能力或部署恢复效果，而不是下一轮采集得到多少可训练示教。本文继承这一原则，并将动作候选与控制权分开建模：残差由视觉和动作历史决定，连续增益以速率受限的状态调节其作用强度，最终再经过安全投影；一次性成功轨迹抑制不必要的修正，纠正区间提供困难状态下的局部行为监督。

### 2.4 交互式模仿学习与持续数据采集闭环

DAgger、ThriftyDAgger、Robot Learning on the Job 以及近期的 intervention-based learning 通过专家查询、人工接管或部署中持续收集数据缓解分布偏移[DAgger, ThriftyDAgger, Robot Learning on the Job, HIL-SERL]。这些工作说明采集、学习和再部署可以形成闭环，但通常把专家查询成本、策略成功率或部署性能作为主要结局，也不必然区分一次性成功、困难状态纠正和不应进入正向训练的冲突样本。本文将闭环目标定义为数据层面的量：在固定操作者时间、reset 数、配置配额和安全预算下，后续采集得到的 $A_{\rm action}$ episode 数是否增加；纠正数据与平滑成功数据共同约束滤波器行为，下游 ACT 或 Diffusion Policy 成功率只作为独立的数据效用验证。

综上，现有研究分别覆盖了示教接口、离线筛选、视觉审计、共享控制和交互式学习，但这些能力通常停留在不同阶段。本文的切入点不是重新提出其中任一模块，而是把它们组织成采集时运行的连续滤波闭环：审计信息定义训练视图，历史示教分别学习动作候选与速率受限的连续辅助增益，真实执行产生新的视觉观测，固定预算实验检验数据产率是否真正提高。

## 3. Method

### 3.1 Task Formulation and Auditable Data Protocol
我们研究一类视觉可观测、物体已经被抓持、目标或任务状态在相机中可见且需要局部轨迹对齐或微调的操作。一个 episode 可抽象为

$$\tau=\{(o_t,u^{\rm raw}_t,u^{\rm exec}_t,q_t,e_t)\}_{t=1}^{T},$$

其中 $o_t$ 是多相机观测，$u^{\rm raw}_t$ 是操作者命令，$u^{\rm exec}_t$ 是实际执行命令，$q_t$ 是机器人状态，$e_t$ 是带时间戳的审计事件。任务阶段可用接近、对齐、局部纠正和短程执行/完成等粗粒度状态描述；具体位置公差、速度上限和成功判据在每个实验配置中预先声明。抓取本身、长时程导航、依赖不可观测力/力矩的控制、严重持续遮挡和柔性物体动力学不在本文范围内。

操作者在每条轨迹上标记一个或多个纠正区间 $I_k=[t^k_s,t^k_e]$，表示从开始修正到恢复完成的时间段。由此定义区间指示量

$$m_t=\mathbf{1}\!\left[t\in\bigcup_k I_k\right]\in\{0,1\}.$$

该指示量用于离线监督与统计。我们将通过终止状态、时间戳完整性、同步一致性和安全事件检查的成功可复用片段定义为动作集合
$A_{\rm action}=\{\tau:\text{episode 通过动作数据准入标准}\}$；失败、near-miss、冲突、掉帧和安全中止片段组成审计集合
$A_{\rm audit}=\{\tau:\text{episode 保留用于质量审计或负例分析}\}$。前者提供正向动作监督，后者保留任务边界和审计信息。终止成功、失败、安全中止、人工接管和配置元数据共同构成每条 episode 的数据契约。数据流为 raw rosbag $\rightarrow$ canonical episode $\rightarrow$ 人工/VLM 审计 $\rightarrow$ correction-aware training view $\rightarrow$ 真实采集闭环。
纠正区间标出示教中需要改变控制行为的时间范围，成功的名义片段则记录了操作者输入已经足够可靠的状态。将两类片段放在同一训练视图中，模型可以从任务上下文学习辅助幅度，在需要修正时逐步介入，在原始动作有效时保持其行为。

### 3.2 Vision-Conditioned Continuous Filter
在时刻 $t$，模型读取过去 $L$ 个时刻的命令、状态和视觉表示：

$$x_t=\{u^{\rm raw}_{t-L:t-1},q_{t-L:t-1},v_{t-L:t}\},\qquad v_t=E_{\rm vis}(o_t).$$

其中 $E_{\rm vis}$ 是冻结的视觉编码器，将多相机观测 $o_t$ 映射为连续视觉表示 $v_t$；本文采用 SigLIP2。离线审计器在较长时间片段上提供阶段、进度、停滞、恢复和纠正候选及其置信度。经人工复核的审计结果用于构造区间标签 $m_t$、终止标签以及 $A_{\rm action}/A_{\rm audit}$ 的数据准入；在线滤波器的上下文 $x_t$ 由视觉、机器人状态和历史命令组成。

命令、状态和视觉 token 经线性投影后输入因果 Transformer，得到上下文表示 $h_t$。条件 VAE 动作头据此表征条件专家动作分布并输出 $\hat u^{\rm exp}_t$；独立的增益头输出增益变化量 $\Delta\alpha_t$：

$$\Delta\alpha_t=r_\alpha\tanh(g_\theta(h_t)),\qquad \alpha_t=\operatorname{clip}(\alpha_{t-1}+\Delta\alpha_t,0,\alpha_{\max}).$$

部署时由动作头与操作者命令的差定义残差：

$$\hat\delta_t=\hat u^{\rm exp}_t-u^{\rm raw}_t,\qquad u^{\rm out}_t=\Pi_{\rm safe}(u^{\rm raw}_t+\alpha_t\hat\delta_t),\quad \alpha_t\in[0,\alpha_{\max}].$$

其中 $\alpha_t$ 是由视觉和动作历史调节的辅助增益，$r_\alpha$ 控制其单步变化幅度，$\Pi_{\rm safe}$ 将组合命令投影到关节位置、速度和变化率约束内。因果注意力使用 $M_{ij}=0$（$j\le i$），否则为 $-\infty$。真实执行改变下一时刻的观测，因此滤波器在新的视觉历史上递推运行。
### 3.3 Corrective Supervision and Offline Training
对 $A_{\rm action}$ 中的同步轨迹，令 $u^{\rm exp}_t$ 表示专家动作记录。训练目标为

$$\mathcal L=\lambda_a\mathcal L_{\rm act}+\lambda_g\mathcal L_{\rm gain}+\lambda_n\mathcal L_{\rm nominal}+\beta\mathcal L_{\rm KL}+\lambda_s\mathcal L_{\rm smooth}.$$

动作项采用区间加权：

$$\mathcal L_{\rm act}=\frac1T\sum_t w_t\|\hat u^{\rm exp}_t-u^{\rm exp}_t\|_1,\quad w_t=1+(w_{\rm corr}-1)m_t.$$

增益项利用纠正区间提供趋势监督：
$\mathcal L_{\rm gain}=T^{-1}\sum_t[m_t\ell_{\rm high}(\alpha_t)+(1-m_t)\ell_{\rm low}(\alpha_t)]$，其中 $\ell_{\rm high}$ 使纠正区间的增益接近预先声明的有效范围，$\ell_{\rm low}$ 约束成功名义片段中的增益保持较小。名义项进一步约束非纠正阶段的动作偏移：
$\mathcal L_{\rm nominal}=T^{-1}\sum_t(1-m_t)\|\hat\delta_t\|_1$。$\mathcal L_{\rm KL}$ 为条件 VAE 先验与后验的 KL 散度，$\mathcal L_{\rm smooth}$ 惩罚输出动作的高频变化。数据准入、审计候选和训练/验证/测试划分的具体流程见第 4 节。
局部修正的方向和作用幅度由不同因素决定：前者取决于专家动作分布，后者取决于当前任务进展以及操作者输入是否已经足够接近目标。因此，模型用动作头产生候选修正，用增益头调节该修正对操作者命令的影响，并通过增益递推限制其变化速度。这样的参数化既保留了专家动作的多模态性，也使辅助强度可以单独测量和校准；后续实验据此分别分析修正方向、增益时序及最终执行效果。

### 3.4 Safe Iterative Data Collection
训练后的模型在真实采集时调用视觉编码器和滤波器完成在线控制，审计器参与离线数据处理。控制链路为 $o_t\rightarrow E_{\rm vis}\rightarrow f_\theta(x_t)\rightarrow\Pi_{\rm safe}\rightarrow u^{\rm out}_t\rightarrow o_{t+1}$。安全层检查 NaN/Inf、残差幅度和变化率、关节/速度限位、模型超时及视觉缺帧，并提供人工旁路和硬件急停。

在第 0 轮开始前，我们冻结参考审计集合 $H_{\rm ref}$ 和数据准入函数 $\Gamma$；$\Gamma$ 包含终止状态、时间同步、缺帧、安全事件和标注置信度等判据。每轮再从候选数据 $D'_r$ 中按预先确定的配置比例随机抽取独立复核集 $H^{(r)}_{\rm audit}$，由人工重新审计并永久排除训练。其余候选数据按相同规则形成下一轮数据：

$$D_r\xrightarrow{\rm train}f_r\xrightarrow{\rm collection}D'_r,\qquad
D_{r+1}=D_r\cup\Gamma\!\left(D'_r\setminus H^{(r)}_{\rm audit}\right).$$

$H_{\rm ref}$ 用于检查审计管线在各轮是否保持一致，$H^{(r)}_{\rm audit}$ 用于估计当轮数据上的错误准入和漏检，$\Gamma$ 的判据和阈值在各轮保持固定。闭环的核心量是单位操作者时间获得的 $A_{\rm action}$ episode 数及其质量，并以此衡量每轮模型更新带来的采集收益。

滤波器的改进最终体现为下一轮采集得到的合格轨迹。固定操作者时间、reset 数和安全预算后，审计结果筛选新轨迹并形成动作训练集，新的动作与增益监督再用于更新滤波器，因而每轮更新都可以用单位操作者时间的合格示教产率来衡量。

## 4. Experiments

我们在真实机器人上评估连续动作滤波器及其数据采集闭环。实验回答三个问题：纠正区间与成功名义片段能否形成可靠而有效的训练监督；滤波器能否学到合适的辅助行为并迁移到未见配置和任务；逐轮更新能否提高单位操作者时间获得的合格示教数量及其下游效用。所有比较固定操作者活跃时间、reset 次数、任务配置配额和安全边界；除特别说明外，控制频率、数据划分和安全投影保持一致。

### 4.1 Experimental Setup and Data Protocol

实验使用与采集系统相同的机器人、同构遥操作接口和多相机视觉。每条 episode 保存同步的 RGB 观测、原始命令 $u^{\rm raw}$、滤波命令、执行命令 $u^{\rm exec}$、机器人状态 $q$、审计事件、纠正区间、终止状态及场景配置。任务均要求物体已被抓持、目标在视觉中可见，并包含接近、对齐、局部纠正或短程执行中的至少一个阶段。成功判据、位置公差、速度限制和安全中止条件在实验前固定。

| 项目 | 配置 | 项目 | 配置 |
| --- | --- | --- | --- |
| 机器人 |  | 遥操作接口 |  |
| 相机与安装位置 |  | 分辨率 / 视觉频率 |  |
| 控制模式 / 频率 |  | 时间同步误差 |  |
| 视觉编码器 | SigLIP2:  | 离线审计器 | Qwen-VL:  |
| 训练硬件 |  | 软件环境与 commit |  |
| 窗口长度 $L$ |  | $\alpha_{\max}$ / $r_\alpha$ |  |
| 操作者研究审批/豁免 |  | 知情同意流程 |  |

考虑到本文关注困难任务中新手操作者的采集效率，我们按遥操作经验预先划分操作者组。每位操作者在正式记录前完成相同的熟悉阶段，并在相同任务配置上依次使用各比较方法；方法顺序采用平衡交叉设计，以降低学习、疲劳和顺序效应。主要产率结果在新手组内进行配对比较，熟练组用于分析辅助收益是否随经验变化。

| 操作者组 | 人数 | 经验划分标准 | 熟悉阶段 | 方法顺序 |
| --- | ---: | --- | --- | --- |
| 新手 |  |  |  |  |
| 熟练 |  |  |  |  |

任务、物体姿态和数据量在下表中填写。表中的公差和安全阈值应在采集前确定，并对所有方法一致。

| 任务 | 任务描述 | 配置数量 | 目标公差 | episode 数 |
| --- | --- | ---: | ---: | ---: |
| T1 |  |  |  |  |
| T2 |  |  |  |  |
| T3 |  |  |  |  |
| 合计 |  |  |  |  |

数据以完整 episode 为单位划分；同一轨迹的相邻窗口不跨越训练、验证和测试集合。第一轮使用人工确认的冷启动数据，后续轮次由审计结果决定哪些片段进入 $A_{\rm action}$。失败、near-miss、冲突和异常片段保留在 $A_{\rm audit}$，用于审计和鲁棒性分析。

| 子集 | episode 数 | 成功 | 含纠正区间 | 失败/异常 | 用途 |
| --- | ---: | ---: | ---: | ---: | --- |
| Train |  |  |  |  | 滤波器训练 |
| Validation |  |  |  |  | 模型选择 |
| Test |  |  |  |  | 主结果 |
| Reference audit $H_{\rm ref}$ |  |  |  |  | 跨轮审计稳定性 |
| Round audit $H^{(r)}_{\rm audit}$ |  |  |  |  | 当轮独立复核 |

每个指标先在 episode 内聚合，再按操作者和任务配置求均值。动作误差、名义动作偏移和纠正区间增益分别为

$$E_{\rm act}=\frac{1}{T}\sum_{t=1}^{T}\|\hat u^{\rm exp}_t-u^{\rm exp}_t\|_1,\qquad
E_{\rm nom}=\frac{1}{|\mathcal N|}\sum_{t\in\mathcal N}\|u^{\rm out}_t-u^{\rm raw}_t\|_1,\qquad
G_{\rm corr}=\frac{1}{|\mathcal C|}\sum_{t\in\mathcal C}\alpha_t,$$

其中 $\mathcal N=\{t:m_t=0\}$、$\mathcal C=\{t:m_t=1\}$。辅助增益对纠正状态的区分度定义为

$$\Delta G=G_{\rm corr}-G_{\rm nom},\qquad G_{\rm nom}=\frac{1}{|\mathcal N|}\sum_{t\in\mathcal N}\alpha_t.$$

我们以 $\alpha_t$ 作为连续分数、$m_t$ 作为参照标签计算 gain AUPRC，并将 $\Delta G$、gain AUPRC 和增益总变差作为辅助时序的主要指标。纠正开始与释放延迟采用验证集上预先确定并冻结的评估阈值 $\eta$ 计算；该阈值仅用于离线统计，同时报告阈值化区间的 IoU。轨迹质量报告速度、加速度和 jerk，延迟、裁剪、旁路和安全事件按每 100 个 episode 归一化。结果报告均值及标准差或 95\% 置信区间，具体重复次数和统计检验填写在表注中。

### 4.2 Auditable Corrective Supervision

我们首先检验可审计示教表示能否稳定地构造训练监督。由第二位标注者对 $H_{\rm ref}$ 独立标记纠正区间和 episode 终止状态，以区间 IoU、active F1、起止时间误差和 success/failure agreement 衡量人工标注的一致性。随后在同一集合上比较人工全量审计、VLM 候选加人工复核和 VLM 候选，报告候选接受率、冲突率、ECE 以及每条 episode 的审计时间。该实验同时给出 $A_{\rm action}$ 和 $A_{\rm audit}$ 的准入一致率，说明审计误差是否会改变动作训练集的组成。

| 审计方案 | 区间 IoU ↑ | Active F1 ↑ | 起止误差 ↓ | 准入一致率 ↑ | 时间/episode ↓ |
| --- | ---: | ---: | ---: | ---: | ---: |
| 独立人工复标 |  |  |  |  |  |
| VLM 候选 + 人工复核 |  |  |  |  |  |
| VLM 候选 |  |  |  |  |  |

监督的有效性通过训练消融评估。Full supervision 同时使用纠正区间的加权动作项、增益趋势项和成功名义片段的低偏移约束；其余变体分别移除纠正监督或名义监督。我们比较动作误差、名义动作偏移、增益区分度、gain AUPRC 和真实执行成功率，从而判断两类片段是否提供互补信息。另以人工标签和经过人工复核的 VLM 候选分别构造训练视图，评估审计方式变化对滤波器的影响。

| 监督设置 | $E_{\rm act}$ ↓ | $E_{\rm nom}$ ↓ | $\Delta G$ ↑ | Gain AUPRC ↑ | 成功率 ↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full supervision |  |  |  |  |  |
| Nominal-only |  |  |  |  |  |
| Correction-only |  |  |  |  |  |
| VLM candidates + review |  |  |  |  |  |

### 4.3 Continuous Assistance and Generalization

我们将完整模型与原始遥操作、固定时序滤波和仅预测轨迹的模型进行比较。所有方法使用相同的控制接口、数据预算和安全投影。结果分别在成功名义片段和包含纠正区间的片段上统计，以同时观察原始动作保留程度与困难状态下的修正效果。

| 方法 | $E_{\rm act}$ ↓ | $E_{\rm nom}$ ↓ | $\Delta G$ ↑ | 增益总变差 ↓ | jerk ↓ | 成功率 ↑ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Raw teleoperation |  |  |  |  |  |  |
| Fixed temporal filter |  |  |  |  |  |  |
| Trajectory-only |  |  |  |  |  |  |
| Full model |  |  |  |  |  |  |

架构消融考察视觉上下文、动作与增益的独立参数化、增益变化率约束和时变增益。除被消融因素外，训练步数、随机种子、数据量和安全参数均保持不变。

| 变体 | $E_{\rm act}$ ↓ | $E_{\rm nom}$ ↓ | $\Delta G$ ↑ | Gain AUPRC ↑ | 成功率 ↑ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full model |  |  |  |  |  |
| w/o visual |  |  |  |  |  |
| Shared action/gain head |  |  |  |  |  |
| w/o rate limit |  |  |  |  |  |
| Fixed gain |  |  |  |  |  |

泛化实验冻结滤波器参数，在未参与训练的 episode、物体姿态和场景配置上运行，并采用按任务留出的测试划分。除动作和增益指标外，我们报告相对于同分布测试的成功率变化，区分配置内插与跨任务迁移的难度。

| 测试设置 | 训练数据 | 测试数据 | $E_{\rm nom}$ ↓ | $\Delta G$ ↑ | Gain AUPRC ↑ | 成功率 ↑ |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| In-distribution |  |  |  |  |  |  |
| Unseen configuration |  |  |  |  |  |  |
| Leave-one-task-out |  |  |  |  |  |  |

### 4.4 Fixed-Budget Flywheel and Downstream Utility

最后，我们在固定操作者活跃时间、reset 次数、场景配置配额和安全预算下比较静态滤波器、单轮训练和逐轮更新的 iterative flywheel。每位操作者在相同配置上完成配对实验，主要结果报告新手组的组内差异，并分别给出新手组和熟练组的效应量。第 $r$ 轮的主要产率为

$$\rho_r=\frac{|A_{\rm action}^{(r)}|}{\operatorname{operator\ minutes}^{(r)}}.$$

每轮记录总尝试数、通过准入的 $A_{\rm action}$ 数量、$A_{\rm audit}$ 数量、操作者时间、安全事件和配置覆盖。结果按操作者经验和任务配置分层，并报告产率随轮次的变化。

| 流程 | $\rho_0$ | $\rho_1$ | $\rho_2$ | 总 $A_{\rm action}$/min ↑ | 成功率 ↑ | 安全事件 ↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Static filter |  |  |  |  |  |  |
| Single-round training |  |  | — |  |  |  |
| Iterative flywheel |  |  |  |  |  |  |

为区分真实的采集改进与审计标准漂移，所有轮次使用冻结的参考集 $H_{\rm ref}$ 和准入函数 $\Gamma$，并从当轮候选数据中抽取互斥的 $H^{(r)}_{\rm audit}$。参考集用于报告审计管线的稳定性，当轮独立复核集用于估计准入 precision、recall 和冲突率。产率提升将与这些审计指标联合报告。

| 轮次 | $\rho_r$ ↑ | Ref. Active F1 ↑ | 准入 precision ↑ | 准入 recall ↑ | 冲突率 ↓ |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 |  |  |  |  |  |
| 1 |  |  |  |  |  |
| 2 |  |  |  |  |  |

为检验准入数据的下游效用，每轮使用相同的 ACT 或 Diffusion Policy 配置训练策略，并在未见 episode 和场景配置上测试。下游数据划分与滤波器训练隔离，策略结果不参与准入规则。报告成功率、达到目标成功率所需的示教数和收敛速度。

| 数据来源 | 训练 episode 数 | 下游策略 | 未见配置成功率 ↑ | 目标成功率所需 episode ↓ | 收敛轮数 ↓ |
| --- | ---: | --- | ---: | ---: | ---: |
| Raw teleoperation |  | ACT / DP |  |  |  |
| Static filter |  | ACT / DP |  |  |  |
| Iteration 1 |  | ACT / DP |  |  |  |
| Iteration 2 |  | ACT / DP |  |  |  |

失败、near-miss、恢复和冲突片段的组成在 $A_{\rm audit}$ 中单独统计，用于判断飞轮是否改变失败类型分布。所有统计量以完整 episode 为单位；显著性检验、重复次数和置信区间计算方式写入最终表注。

## 5. Limitations

本文以人工确认的冷启动数据为起点，纠正区间的边界会受到操作者反应延迟和标注者判断差异的影响。独立复标、参考审计集和逐轮抽检能够量化这种不确定性，但仍保留了人工审计成本；当任务阶段难以从视觉中辨认或训练分布发生较大变化时，离线 VLM 候选也可能降低审计效率。

当前方法面向物体已被抓持、目标视觉可见且以局部对齐或短程微调为主的任务。实验结论不直接覆盖抓取、长时程导航、持续遮挡、依赖力/力矩反馈的接触操作和柔性物体控制。残差幅度、增益变化率和安全投影边界仍按机器人与任务配置设定，跨 embodiment 的动作语义和统一参数化有待进一步研究。

操作者实验能够比较不同经验水平下的采集收益，但有限的参与者、任务种类和闭环轮数仍会限制统计外推。下游 ACT 或 Diffusion Policy 的结果用于衡量准入数据在所选模仿学习器上的效用，尚不能推出对所有策略架构和更大规模数据训练同样成立。

## 6. Conclusion

本文研究如何利用已有的可审计示教改善下一轮真实机器人遥操作采集。成功名义片段与纠正区间共同构成训练监督：前者约束正常状态下的动作保留，后者提供困难状态中的局部修正信息。在此基础上，视觉条件化滤波器分别预测候选专家动作和连续辅助增益，并通过有界残差、增益速率约束与安全投影接入控制链路。

该方法将模型评价从离线动作拟合延伸到真实的数据采集过程。固定参考审计集、逐轮独立复核和统一数据准入规则用于保持跨轮比较的一致性；固定操作者预算下的合格示教产率衡量采集效率，下游模仿学习则检验新增数据是否具有训练价值。由此，审计、辅助和再采集被组织为一个可测量的闭环，为视觉可观测精细操作中的高质量真机数据采集提供了明确的研究与实验框架。

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
