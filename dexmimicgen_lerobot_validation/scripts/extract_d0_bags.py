#!/usr/bin/env python3
"""Extract right-arm + O6 + color frames from D0 ROS2 bags.

This script intentionally runs with the ROS Humble system Python.  The output
is a small NumPy interchange file that the Conda LeRobot environment can read.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


COLOR_TOPIC = "/camera/camera/color/image_raw"
STATE_TOPIC = "/robot1/right_arm/joint_states"
ARM_ACTION_TOPIC = "/right_arm_joint_control"
HAND_ACTION_TOPIC = "/robot1/right_hand/set_l6_joint"


def reader_for(bag: Path):
    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag), storage_id="sqlite3"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    type_map = {
        info.name: get_message(info.type)
        for info in reader.get_all_topics_and_types()
    }
    return reader, type_map


def image_to_rgb(message) -> np.ndarray:
    encoding = str(message.encoding).lower()
    channels = 3 if encoding in {"rgb8", "bgr8"} else 1
    dtype = np.uint16 if encoding in {"16uc1", "mono16"} else np.uint8
    values = np.frombuffer(message.data, dtype=dtype)
    row_width = int(message.step) // np.dtype(dtype).itemsize
    if channels == 3:
        image = values.reshape(int(message.height), row_width // 3, 3)[
            :, : int(message.width), :
        ]
        if encoding == "bgr8":
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        image = values.reshape(int(message.height), row_width)[:, : int(message.width)]
        if image.dtype != np.uint8:
            image = np.clip(image / 256.0, 0, 255).astype(np.uint8)
        image = np.repeat(image[:, :, None], 3, axis=2)
    return cv2.resize(image, (84, 84), interpolation=cv2.INTER_AREA)


def append_series(series: dict[str, list], key: str, stamp: int, values) -> None:
    values = np.asarray(values, dtype=np.float32)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        return
    series[key].append((int(stamp), values.copy()))


def first_pass(bag: Path):
    reader, type_map = reader_for(bag)
    required = {COLOR_TOPIC, STATE_TOPIC, ARM_ACTION_TOPIC, HAND_ACTION_TOPIC}
    missing = sorted(required - type_map.keys())
    if missing:
        raise RuntimeError(f"{bag}: missing topics: {missing}")

    image_times: list[int] = []
    series: dict[str, list] = {"state": [], "arm_action": [], "hand_action": []}
    while reader.has_next():
        topic, raw, stamp = reader.read_next()
        if topic == COLOR_TOPIC:
            image_times.append(int(stamp))
            continue
        if topic not in {STATE_TOPIC, ARM_ACTION_TOPIC, HAND_ACTION_TOPIC}:
            continue
        message = deserialize_message(raw, type_map[topic])
        if topic == STATE_TOPIC and len(message.position) >= 7:
            append_series(series, "state", stamp, message.position[:7])
        elif topic == ARM_ACTION_TOPIC and len(message.position) >= 7:
            append_series(series, "arm_action", stamp, message.position[:7])
        elif topic == HAND_ACTION_TOPIC and len(message.data) >= 6:
            append_series(
                series,
                "hand_action",
                stamp,
                np.asarray(message.data[:6], dtype=np.float32) / 255.0,
            )

    if not image_times or any(not series[key] for key in series):
        raise RuntimeError(f"{bag}: one or more required streams are empty")
    return image_times, series, type_map


def previous_value(values: list[tuple[int, np.ndarray]], stamp: int) -> np.ndarray:
    times = np.asarray([item[0] for item in values], dtype=np.int64)
    index = int(np.searchsorted(times, stamp, side="right") - 1)
    return values[max(0, min(index, len(values) - 1))][1]


def extract_episode(bag: Path, output: Path, fps: int) -> dict[str, object]:
    image_times, series, type_map = first_pass(bag)
    start = max(
        image_times[0], *(values[0][0] for values in series.values())
    )
    end = min(
        image_times[-1], *(values[-1][0] for values in series.values())
    )
    if end <= start:
        raise RuntimeError(f"{bag}: no common time interval")

    step_ns = int(round(1_000_000_000 / fps))
    target_times = np.arange(start, end + 1, step_ns, dtype=np.int64)
    image_times_array = np.asarray(image_times, dtype=np.int64)
    image_indices: list[int] = []
    for stamp in target_times:
        right = int(np.searchsorted(image_times_array, stamp, side="left"))
        candidates = [max(0, min(right, len(image_times) - 1))]
        if right > 0:
            candidates.append(right - 1)
        image_indices.append(min(candidates, key=lambda index: abs(image_times[index] - stamp)))
    wanted_images = {index: frame for frame, index in enumerate(image_indices)}
    images: list[np.ndarray | None] = [None] * len(target_times)

    reader, _ = reader_for(bag)
    color_index = 0
    while reader.has_next():
        topic, raw, _stamp = reader.read_next()
        if topic != COLOR_TOPIC:
            continue
        frame = wanted_images.get(color_index)
        if frame is not None:
            message = deserialize_message(raw, type_map[COLOR_TOPIC])
            images[frame] = image_to_rgb(message)
        color_index += 1

    if any(image is None for image in images):
        raise RuntimeError(f"{bag}: failed to decode one or more color frames")
    image_array = np.stack([image for image in images if image is not None]).astype(np.uint8)
    states = np.stack(
        [
            np.concatenate(
                [
                    previous_value(series["state"], int(stamp)),
                    previous_value(series["hand_action"], int(stamp)),
                ]
            )
            for stamp in target_times
        ]
    ).astype(np.float32)
    actions = np.stack(
        [
            np.concatenate(
                [
                    previous_value(series["arm_action"], int(stamp)),
                    previous_value(series["hand_action"], int(stamp)),
                ]
            )
            for stamp in target_times
        ]
    ).astype(np.float32)

    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        images=image_array,
        states=states,
        actions=actions,
        timestamps=(target_times - start).astype(np.float64) / 1_000_000_000.0,
    )
    summary = {
        "bag": str(bag),
        "output": str(output),
        "fps": fps,
        "frames": int(len(target_times)),
        "state_dim": int(states.shape[1]),
        "action_dim": int(actions.shape[1]),
        "image_shape": list(image_array.shape[1:]),
        "duration_s": float((end - start) / 1_000_000_000.0),
    }
    output.with_suffix(".json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bags", nargs="+", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=10)
    args = parser.parse_args()
    if args.fps <= 0:
        parser.error("--fps must be positive")
    for bag in args.bags:
        # The supplied path is .../<episode-id>/bag.
        episode_id = bag.parent.name
        summary = extract_episode(
            bag,
            args.output_dir / f"{episode_id}.npz",
            args.fps,
        )
        print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
