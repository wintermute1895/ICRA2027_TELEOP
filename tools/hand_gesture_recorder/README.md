# Hand gesture recorder

录制 L10/O6 的实时姿势，生成可直接导入的 Python 文件和 JSON 备份。

```bash
python -m tools.hand_gesture_recorder.recorder --hand L10 --side left
python -m tools.hand_gesture_recorder.recorder --hand O6 --simulate
```

按数字键选择光标关节（L10 可按 `0` 选择第 10 个关节），按空格将光标关节加入/移出多选集合；`a` 全选，`x` 清空选择。方向键会同时调节多选集合（若集合为空则调节光标关节），`r` 重新读取硬件实际状态，`s` 保存下一个编号（0、1、2…），`q` 退出。界面会固定刷新并显示所有自由度的当前数值，避免终端滚屏。生成文件位于 `gestures/`，例如 `from gestures.l10_gestures import GESTURES`。L10 通过仓库 `LinkerHand` CAN SDK，O6 通过 vendored `linkerbot` SDK；两者均需先正确配置 CAN。`--simulate` 可离线测试界面。

如果输出目录中已有同一手型的 JSON 文件，重新启动会自动读取已有手势，并从当前最大编号加一继续录制。例如已有 `0`、`1`，下一次保存就是 `2`。启动时不会清除旧手势。

录制完成后，可用图形界面执行手势：

```bash
python -m tools.hand_gesture_player --hand L10 --side right --can can0 --output gestures
```

点击窗口聚焦，按 `0`/`1`/`2` 选择，按 Enter 执行整组姿势，按 Esc 退出。选择数字不会运动手部；只有 Enter 会发送指令。没有硬件时可加 `--simulate`。
