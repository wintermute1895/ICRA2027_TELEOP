#!/usr/bin/env python3
"""Split a recorded D0 bag into A_action or A_audit.

This is deliberately a first version.  It checks the W3 admission criteria that
can be checked automatically today:

  * task configuration exists
  * causal chain topics are present and non-empty
  * header timestamps are monotonic and aligned within a configured skew
  * no joint fault was recorded in /joint_error_code
  * no unlogged external override is declared
  * terminal insertion is marked successful

Unknown or failed terminal state is routed to ``A_audit`` rather than silently
guessed as success.
"""

from __future__ import annotations

import argparse
import bisect
import json
from pathlib import Path

import rosbag2_py
from rosidl_runtime_py.utilities import get_message
from rclpy.serialization import deserialize_message


def load_manifest(manifest_path: Path) -> dict[str, object]:
    if not manifest_path.is_file():
        raise SystemExit(f"missing recording manifest: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def required_topics(
    manifest: dict[str, object],
) -> tuple[list[str], list[str], list[str], list[str]]:
    topics = [str(t) for t in manifest.get("topics", [])]
    arm = str(manifest.get("arm", "right"))
    arms = ["left", "right"] if arm == "both" else [arm]
    master_topics = ["/joint_error_code"]
    for side in arms:
        master_topics.extend(
            [
                f"/{side}_arm_joint_control",
                f"/vist/{side}/master_joint_raw",
                f"/vist/{side}/master_joint_filtered",
                f"/vist/{side}/mapped_joint_command",
            ]
        )
    robot_namespace = str(manifest.get("robot_namespace", "robot1")).strip("/")
    robot_topics: list[str] = []
    if manifest.get("require_robot_state"):
        for side in arms:
            robot_topics.extend(
                [
                    f"/{robot_namespace}/{side}_arm/joint_states",
                    f"/{robot_namespace}/{side}_arm/pose_states",
                ]
            )
    camera_topics = [str(t) for t in manifest.get("camera_topics", [])]
    hand_topics = [str(t) for t in manifest.get("hand_topics", [])]
    # Preserve only topics that were actually requested by the recorder.
    requested = set(topics)
    return [t for t in master_topics if t in requested], [
        t for t in robot_topics if t in requested
    ], [t for t in camera_topics if t in requested], [
        t for t in hand_topics if t in requested
    ]


def header_stamp_ns(message: object) -> int | None:
    header = getattr(message, "header", None)
    if header is None:
        return None
    stamp = getattr(header, "stamp", None)
    if stamp is None:
        return None
    sec = getattr(stamp, "sec", None)
    nanosec = getattr(stamp, "nanosec", None)
    if sec is None or nanosec is None:
        return None
    return int(sec) * 1_000_000_000 + int(nanosec)


def joint_fault(data: str) -> bool:
    # LinkerTA publishes a string like "J0:0, J1:0, ... J13:0, ".
    for field in data.replace(" ", "").split(","):
        if not field:
            continue
        try:
            name, value = field.split(":")
            if name.startswith("J") and int(value) != 0:
                return True
        except ValueError:
            continue
    return False


def read_bag(bag_dir: Path) -> tuple[dict[str, object], list[str]]:
    if not bag_dir.is_dir():
        raise SystemExit(f"bag directory not found: {bag_dir}")

    reader = rosbag2_py.SequentialReader()
    storage_options = rosbag2_py.StorageOptions(uri=str(bag_dir), storage_id="sqlite3")
    converter_options = rosbag2_py.ConverterOptions(
        input_serialization_format="cdr",
        output_serialization_format="cdr",
    )
    reader.open(storage_options, converter_options)

    type_map = {
        item.name: item.type
        for item in reader.get_all_topics_and_types()
    }
    counters: dict[str, dict[str, object]] = {}
    reasons: list[str] = []
    safety_fault = False
    seqs: dict[str, list[int]] = {}

    while reader.has_next():
        topic, serialized, receipt_ns = reader.read_next()
        counter = counters.setdefault(
            topic,
            {
                "count": 0,
                "first_header_ns": None,
                "last_header_ns": None,
                "first_receipt_ns": receipt_ns,
                "last_receipt_ns": receipt_ns,
                "max_header_receipt_skew_ms": 0.0,
                "max_header_backjump_ms": 0.0,
                "header_inversions": 0,
                "invalid_hand_messages": 0,
            },
        )
        counter["count"] = int(counter["count"]) + 1
        counter["last_receipt_ns"] = receipt_ns

        message_type = type_map.get(topic)
        message = None
        if message_type:
            message = deserialize_message(serialized, get_message(message_type))

        # The current lbot driver accepts hand commands as UInt8MultiArray.
        # Validate the expected joint count so a publisher emitting empty or
        # malformed arrays cannot make an episode look complete.
        expected_hand_len = None
        if topic.endswith("_hand/set_l10_joint"):
            expected_hand_len = 10
        elif topic.endswith("_hand/set_l6_joint"):
            expected_hand_len = 6
        if expected_hand_len is not None:
            data = getattr(message, "data", None)
            if data is None or len(data) != expected_hand_len:
                counter["invalid_hand_messages"] = (
                    int(counter["invalid_hand_messages"]) + 1
                )

        header_ns = header_stamp_ns(message) if message is not None else None
        if header_ns is not None:
            seqs.setdefault(topic, []).append(header_ns)
            counter["max_header_receipt_skew_ms"] = max(
                float(counter["max_header_receipt_skew_ms"]),
                abs(header_ns - int(receipt_ns)) / 1_000_000.0,
            )
            if counter["first_header_ns"] is None:
                counter["first_header_ns"] = header_ns
            if (
                counter["last_header_ns"] is not None
                and header_ns < int(counter["last_header_ns"])
            ):
                backjump_ms = (int(counter["last_header_ns"]) - header_ns) / 1_000_000.0
                counter["max_header_backjump_ms"] = max(
                    float(counter["max_header_backjump_ms"]), backjump_ms
                )
                counter["header_inversions"] = int(counter["header_inversions"]) + 1
            counter["last_header_ns"] = header_ns

        if topic == "/joint_error_code" and message is not None:
            if joint_fault(str(message.data)):
                safety_fault = True

    return {
        "counters": counters,
        "seqs": seqs,
        "safety_fault": safety_fault,
        "audit_reasons": reasons,
    }, list(type_map.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--out-root", type=Path, default=Path("d0_data"))
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument(
        "--success",
        choices=("true", "false", "unknown"),
        default="unknown",
        help="Terminal insertion audit result. Unknown always routes to A_audit.",
    )
    parser.add_argument("--max-skew-ms", type=float, default=250.0)
    parser.add_argument(
        "--max-header-backjump-ms",
        type=float,
        default=100.0,
        help="Maximum tolerable backward header jump caused by late bag delivery.",
    )
    parser.add_argument(
        "--max-header-inversions",
        type=int,
        default=5,
        help="Maximum number of tolerated out-of-order header messages per topic.",
    )
    args = parser.parse_args()

    episode_dir = args.out_root / args.episode_id
    manifest_path = args.manifest or (episode_dir / "recording_manifest.json")
    manifest = load_manifest(manifest_path)
    bag_dir = Path(str(manifest.get("bag_dir") or episode_dir / "bag"))
    bag_dir = Path(str(episode_dir / "bag") if not bag_dir.is_dir() else bag_dir)

    master_required, robot_required, camera_required, hand_required = required_topics(manifest)
    stats, _ = read_bag(bag_dir)
    counters = stats["counters"]
    seqs = stats.get("seqs", {})
    reasons: list[str] = []

    required = [*master_required, *robot_required, *camera_required, *hand_required]
    for topic in required:
        if topic not in counters or int(counters[topic]["count"]) <= 0:
            reasons.append(f"missing_or_empty_topic:{topic}")

    for topic in required:
        counter = counters.get(topic)
        if not counter:
            continue
        invalid_hand_messages = int(counter.get("invalid_hand_messages", 0))
        if invalid_hand_messages:
            reasons.append(
                f"invalid_hand_message_count:{topic}:{invalid_hand_messages}"
            )
        inversions = int(counter.get("header_inversions", 0))
        backjump_ms = float(counter.get("max_header_backjump_ms", 0.0))
        if inversions > args.max_header_inversions:
            reasons.append(
                f"header_time_inversion_count:{topic}:{inversions}"
            )
        if backjump_ms > args.max_header_backjump_ms:
            reasons.append(
                f"header_backjump_too_large:{topic}:{backjump_ms:.1f}ms"
            )
        if float(counter.get("max_header_receipt_skew_ms", 0.0)) > args.max_skew_ms:
            reasons.append(
                f"header_receipt_skew_too_large:{topic}:"
                f"{float(counter.get('max_header_receipt_skew_ms', 0.0)):.1f}ms"
            )

    if str(manifest.get("external_override", "logged")) == "unlogged":
        reasons.append("unlogged_external_override")
    if stats.get("safety_fault"):
        reasons.append("joint_fault_recorded")
    if args.success != "true":
        reasons.append(f"terminal_insertion_not_success:{args.success}")

    accepted = not reasons
    split = "A_action" if accepted else "A_audit"
    output_dir = args.out_root / split
    output_dir.mkdir(parents=True, exist_ok=True)

    camera_sync: dict[str, object] = {}
    if robot_required:
        robot_seq = seqs.get(robot_required[0], [])
        for cam in camera_required:
            cam_seq = seqs.get(cam, [])
            if not robot_seq or not cam_seq:
                camera_sync[cam] = {"n": len(cam_seq), "error": "no robot state sequence"}
                continue
            deltas = []
            for header_ns in cam_seq:
                i = bisect.bisect_left(robot_seq, header_ns)
                candidates = []
                if i > 0:
                    candidates.append(header_ns - robot_seq[i - 1])
                if i < len(robot_seq):
                    candidates.append(robot_seq[i] - header_ns)
                deltas.append(min(candidates) / 1_000_000.0)
            deltas.sort()
            n = len(deltas)
            sync_stats = {
                "n": n,
                "median_ms": round(deltas[n // 2], 2),
                "p95_ms": round(deltas[min(int(n * 0.95), n - 1)], 2),
                "max_ms": round(deltas[-1], 2),
            }
            camera_sync[cam] = sync_stats
            print(
                f"CAMERA_SYNC={cam}: n={n} "
                f"median={sync_stats['median_ms']}ms "
                f"p95={sync_stats['p95_ms']}ms max={sync_stats['max_ms']}ms"
            )

    report = {
        "schema": "d0.split-report/v1",
        "episode_id": args.episode_id,
        "split": split,
        "accepted": accepted,
        "reasons": reasons,
        "topics": {
            topic: counters.get(topic)
            for topic in required
        },
        "hand_topics": hand_required,
        "camera_sync": camera_sync,
        "bag_dir": str(bag_dir),
        "manifest_path": str(manifest_path),
    }
    output_path = output_dir / f"{args.episode_id}.json"
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"SPLIT={split}")
    print(f"REPORT={output_path}")
    for reason in reasons:
        print(f"REASON={reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
