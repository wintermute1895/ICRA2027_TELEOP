# Python/Tk Capture Manager

## Why this exists

The previous `start_capture_session.sh` used tmux windows as both the process
manager and the recorder terminal.  On this machine the failure looked like:

```text
server exited unexpectedly
```

The real cause was a client/server tmux version mismatch.  When launched from
the `teleop` Conda environment, the script started a tmux **3.7** server, while
new terminals used the system `/usr/bin/tmux` **3.2a**.  The two versions cannot
speak the same protocol, so attach commands failed even though the server and
its ROS children were still alive.

Instead of continuing to depend on tmux, the new backend is a Python supervisor
with an optional Tkinter GUI.  It keeps `tools/capture_episode.py` as the owner
of each episode and does not change ROS topics, RunEvidence output, audit
contracts, or ACT conversion.

## Files

| File | Purpose |
|---|---|
| `tools/capture_manager.py` | supervisor and GUI; starts/monitors/stops the ROS graph and recorder |
| `scripts/start_capture_gui.sh` | safe entry point that opens the GUI after all launcher validation |
| `scripts/start_capture_session.sh` | `python` backend is now the default; use `--manager=gui` for the GUI, or `--manager=tmux` for the legacy tmux backend |
| `scripts/stop_capture_session.sh` | stops either backend without deleting evidence |

## Usage

### GUI manager

```bash
bash scripts/start_capture_gui.sh \
  --real \
  --physical-estop-ready \
  --confirm=I_UNDERSTAND_REAL_ROBOT \
  --task-id=task2 \
  --arms=right \
  --episodes=0 \
  --manual-segments \
  --second-camera-serial=327122074150 \
  --data-root="/media/fanshihao/Cyan_data/ICRA2027_TELEOP_DATA/evidence/teleop"
```

Safe observation mode (no `--real`) does not need the E-stop confirmation.

### Foreground Python supervisor (no GUI)

This is also the default backend, so `--manager=python` can be omitted.

```bash
bash scripts/start_capture_session.sh \
  --manager=python \
  --manual-segments \
  --episodes=0 \
  --data-root="/media/fanshihao/Cyan_data/ICRA2027_TELEOP_DATA/evidence/teleop"
```

In this mode the recorder remains attached to the invoking terminal, exactly
like the old recorder window: Enter starts/stops an episode, `1`-`9`/`0`
annotate, and `q` exits.

## GUI behavior

* **开始/结束 Episode** sends the same Enter key the recorder would receive.
* **标注键 1-9/0** sends an annotation while recording.
* **审计: 成功 / 审计: 失败 / 跳过审计** answers the recorder's terminal audit
  prompts without bypassing them.
* **安全停止并退出** first asks the recorder to close the current episode and
  audit, then stops ROS nodes in reverse launch order.
* Closing the GUI window performs the same safe stop.

Global keyboard shortcuts (the text input field is excluded):

* `Enter`: start/stop the current episode, same as the episode button.
* `1`-`9`, `0`: live annotation while recording.
* `q`: exit the recorder loop when it is in the ready/closed state.

The text input field is for audit answers or other terminal text.  An empty
input is intentionally not sent, so a stray Enter cannot skip the audit.

Real-hardware confirmations are never bypassed by the GUI.  They are enforced by
`start_capture_session.sh` before the manager is launched.

## Logs and state

Each session writes under the selected data root:

```text
<data-root>/system/supervisor/<session>-<utc>/
├── logs/
│   ├── driver.log
│   ├── camera.log
│   ├── camera2.log
│   ├── teleop.log
│   └── ...
└── session_state.json
```

`session_state.json` contains manager PID, per-component PIDs, status, and log
paths.  A small locator file in `/tmp` lets `scripts/stop_capture_session.sh`
find the correct state even when the data root is an external disk.
