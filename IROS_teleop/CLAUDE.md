# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vision-based bilateral robot teleoperation prototype using MediaPipe hand tracking + RealSense D435i depth camera → Pink IK solver → simulated LinkerBot arms and LinkerHand dexterous hands, visualized in Meshcat. Part of the LinkerBot ecosystem.

## Install & Run

```bash
pip install -r requirements.txt
```

### With real camera

```bash
python vision_pose.py          # Terminal 1: camera + MediaPipe → UDP on port 5005
python control_anyteleop.py    # Terminal 2: receives UDP, runs IK, drives Meshcat visualization
```

### Without camera (mock testing)

```bash
python mock_vision.py          # Generates synthetic open/close hand trajectories via UDP
python control_anyteleop.py   # Consumes mock data
```

### URDF inspection

```bash
python check.py                # Prints all joint/link names from combined URDF
```

## Architecture

```
RealSense D435i → MediaPipe Hands → 3D keypoints
  → UDP (JSON, port 5005)
    → control_anyteleop.py: ThumbFixController
      → mirror + scale + thumb rotation correction
      → Pinocchio FK + Pink IK
      → Meshcat browser visualization
```

### Key files

| File | Role |
|------|------|
| `control_anyteleop.py` | Main teleop loop: `ThumbFixController` receives UDP, runs dex-retargeting, solves IK, drives Meshcat |
| `vision_pose.py` | Camera client: RealSense + MediaPipe Pose + Hands → UDP JSON packets |
| `mock_vision.py` | Mock client: synthetic hand trajectories (open/close) for testing without camera |
| `check.py` | URDF inspection: loads combined URDF, prints all joint/link names |
| `Remote Robot/body_hand_track.py` | Standalone body+hand recorder using MediaPipe Holistic, outputs `teleop_record.json` |
| `lbot/` | `LbotRobot`/`LbotAPI` classes — TCP bridge to real LinkerBot robot controller (192.168.10.21) |

### Other content

- `config/` — combined robot URDF (LKLS73 O2 dual arms + L10 hands), joint name dictionaries
- `Remote Robot/` — full-body recording tools for data collection

## Dependencies

pinocchio, pink, meshcat, mediapipe, opencv-python, pyrealsense2, scipy, numpy
