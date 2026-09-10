# 3 个 Task 的 ACT 实验记录

> 用途:跟踪每个 task 的 ACT 模型轮换(训练 → promote → validate → 冒烟 → 真机)。
> 轮换流程见个人笔记 `~/Desktop/knowledge/ICRA2027/ACT模型部署_v2.md`「模型轮换工作流」。
> 排障参考 `~/Desktop/knowledge/ICRA2027/数采+act+推理问题.md` 与 `docs/问题与解决.md`。

## 约定

- 每个模型的 promoted yaml 命名 `config/runtime/act-<task>-<round>.yaml`,晋升后不改内容;
- 真机 bag 存 `act_rollouts/<task>/<round>/`(当前数据盘:`/media/fanshihao/robot_data/ICRA2027_Data/act_rollouts/`);
- ACT 部署只有 active 模式:冒烟确认软件就绪后,必须经人工安全确认直接真机;
- active 需 `--confirm=I_UNDERSTAND_REAL_ROLLOUT` + `--model-confirm=I_UNDERSTAND_MODEL_DEPLOYMENT`,且必须用 `rollout_active_test.yaml`(门限 0.6,勿用 filter 的 0.05);
- 已知遗留:相机 15Hz / ACT 10Hz / 机械臂 50Hz 频率不匹配。

## Task1 精密对准(precision_alignment)

| Round | 日期 | checkpoint | dataset stats | promoted yaml | validate | 冒烟 | 真机 | 备注 |
|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | 已有 act_task1_v6_clean_b32_w12(旧,未走 promote) |

## Task2 电源按钮(power_button_press_v1)

| Round | 日期 | checkpoint | dataset stats | promoted yaml | validate | 冒烟 | 真机 | 备注 |
|---|---|---|---|---|---|---|---|---|
| button_A | 2026-09-09 验证 | `models/act_button_A/checkpoints/last/pretrained_model` | `models/act_button_A/stats.json` | `config/runtime/act-button-A.yaml` | ✅ SHA-256 通过 | ✅ worker 5.1s READY | 待做 | 曾真机推理通但效果差,疑频率链问题 |
| task2-50hz(98ep,100ep) | 2026-09-09 promote | `robot_data/.../task2_button_press_50hz_20260908T171908Z/checkpoints/466900/pretrained_model` | `lerobot_task2_button_press_50hz/meta/stats.json`(当日聚合生成) | `config/runtime/act-task2-50hz.yaml` | ✅ SHA-256 通过 | ✅ worker 3.0s READY | **下一步** | Dex 服务器训练(09-08);98 集 50Hz;注意 robot_data 盘需保持挂载 |

## Task3 螺丝刀对准(screwdriver_alignment_v1)

| Round | 日期 | checkpoint | dataset stats | promoted yaml | validate | 冒烟 | 真机 | 备注 |
|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | 未训练 |

## 待办

1. 频率链问题闭环(15/10/50Hz)前,真机效果存疑,优先解决
2. Task1/Task3 模型训练后排进轮换流水线
