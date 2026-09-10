# 3 个 Task 的 Filter 实验记录

> 用途:跟踪每个 task 的 filter 链路进度(数采 → prepare → train → eval → promote → 真机部署 → 迭代)。
> 执行指令集见个人笔记 `~/Desktop/knowledge/ICRA2027/3个task的完整流程.md`;排障参考 `docs/问题与解决.md`。
> 数据盘(临时):`/media/fanshihao/Cyan_data/ICRA2027_DATA/Task_Data/`(8T 机械盘备份暂不可用,恢复后路径需整体迁移回 `Seagate Hub`)。

## 当前进度总览(2026-09-08)

| 环节 | Task1 精密对准 | Task2 电源按钮 | Task3 螺丝刀对准 |
|---|---|---|---|
| Episode 数 | 60 | 52 | 100 |
| ② prepare | ✅ 24 视图(09-08) | ❌ 未执行(0 视图) | ❌ 未执行(0 视图) |
| ③ round1 训练 | ❌ 未执行 | ❌ 未执行* | ❌ 未执行 |
| ④ 离线评估 | — | — | — |
| ⑤ promote | — | — | — |
| ⑥ 真机部署 | — | — | — |

\* Task2 曾于 2026-09-06 在旧盘(`UBUNTU 20_0/task_button_press`)完整跑通过 round1(30 视图、27 train / 3 val、部署边界候选验证),产物随旧盘路径失效,当前数据盘上需重跑。工程链路已验证,详见 `docs/问题与解决.md`。

统一约定:
- 训练 round 命名 `round1/round2/...`,禁止覆盖已有 round;
- 每次迭代更新本文件对应 task 的「迭代记录」;
- filter 部署只有 active 模式(与 ACT 一致);部署 = 冒烟验证 worker/adapter 就绪后,经显式人工安全确认直接真机 active。

## ⚠ 当前阻塞:等待新 filter 架构(2026-09-08 决策)

远端分支 `origin/exp/continuous-filter-backbone-spike`(cx)正在重写 filter:二值 correction gate → 连续速率受限增益(horizon=8 动作块 + 独立 gain 头 + α 限速),并带 9 变体消融器(`tools/run_filter_ablations.py`)。**决策:暂停本机旧架构的训练,等该分支更新稳定后合并,直接用新方法跑三个 task 的 round1**。届时需注意:
1. merge 时 `tools/learned_filter_ros_adapter.py` 与本地 diag 日志节流改动有冲突,保留本地节流;
2. 新模型配置(horizon/gain 参数)与旧 worker 不兼容,代码/配置/worker 必须同版本,相关文档与个人笔记(`3个task的完整流程.md`、`Filter.md`)同步更新;
3. Task1 已 prepare 的 24 个视图数据格式不变,可直接复用。

## Task1 精密对准(precision_alignment)

- flywheel 配置:`config/flywheel/task1_precision_alignment_local.yaml`(derived_name `task1_precision_alignment_v1`,validation 3)
- 采集 env:`config/capture_session.env`;filter 配置需在会话 env 中显式指定 promoted runtime YAML
- ⚠ 注意:Task1 采集 env 默认无标注键位映射,补采时需确认 correction(4 键)标注可用,否则学不出修正能力

### 迭代记录

| Round | 日期 | 数据(prepare 结果) | train/val | 评估关键指标 | 产物路径 | 部署 | 备注 |
|---|---|---|---|---|---|---|---|
| round1 | 2026-09-08 prepare 完成 | attempted=24 failed=36 views=24(21 质量门 review + 5 缺 audit + 10 导出/其他) | — | — | `Task1_Data/filter_runs/logs/prepare_20260908T123633Z.log` | — | 待训练(views=24 ≥ 4) |

## Task2 电源按钮(power_button_press_v1)

- flywheel 配置:`config/flywheel/task2_button_press_local.yaml`(derived_name `task2_button_press_v1`,validation 3)
- 采集 env:`config/capture_session_task2.env`;filter 配置需在会话 env 中显式指定 promoted runtime YAML
- 标注键位:3=press、4=correction_toggle、7=verify、9=成功、0=失败

### 迭代记录

| Round | 日期 | 数据(prepare 结果) | train/val | 评估关键指标 | 产物路径 | 部署 | 备注 |
|---|---|---|---|---|---|---|---|
| round1(旧盘) | 2026-09-06 | attempted=30 failed=23 views=30 | 27/3 | MAE≈0.0605 rad,corr prob≈1e-4 | `UBUNTU 20_0/task_button_press/filter_runs/round1/`(已失效) | (历史)候选链路验证通过 | correction 概率近 0,仅工程验证;记录见 `docs/问题与解决.md` |
| round1(Cyan_data) | 未开始 | — | — | — | — | — | 待执行 prepare |

## Task3 螺丝刀对准(screwdriver_alignment_v1)

- flywheel 配置:`config/flywheel/task3_screwdriver_local.yaml`(derived_name `task3_screwdriver_v1`,validation 10)
- 采集 env:`config/capture_session_task3.env`;filter 配置需在会话 env 中显式指定 promoted runtime YAML
- 标注键位:3=verify、4=correction_toggle、7=target_lost、9=成功、0=失败

### 迭代记录

| Round | 日期 | 数据(prepare 结果) | train/val | 评估关键指标 | 产物路径 | 部署 | 备注 |
|---|---|---|---|---|---|---|---|
| round1 | 未开始 | — | — | — | — | — | 待执行 prepare |

## 产物路径模板(Cyan_data)

```text
/media/fanshihao/Cyan_data/ICRA2027_DATA/Task_Data/<TaskN_Data>/
└── filter_runs/
    ├── logs/{prepare,train_roundN,eval_roundN,promote_roundN}_<UTC>.log
    └── roundN/
        ├── model/trajectory_filter.pt + training_report.json
        ├── validation_views.txt
        ├── tensorboard/
        ├── evaluation/evaluation_report.json + predictions.jsonl
        └── filter-promoted-roundN.yaml
```

## 待办

1. **(阻塞中)**等 `exp/continuous-filter-backbone-spike` 稳定 → merge 到本机 → 用新架构跑 Task1 round1(数据已就绪)
2. Task2/Task3 执行 prepare(确认 `prepared_views` 数量后更新本文件)
3. Task1 标注键位映射确认/补齐
4. 8T 机械盘恢复后,路径整体迁回 `Seagate Hub`(sed 替换 `Cyan_data/ICRA2027_DATA/Task_Data` → `Seagate Hub/ICRA2027`,注意 task1/2 目录大小写)




# 实验进度记录

## Task1
Round               数据数量               filter模型产出路径
  1                   60
