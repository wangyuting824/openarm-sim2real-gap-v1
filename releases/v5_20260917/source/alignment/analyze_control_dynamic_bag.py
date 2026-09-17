#!/usr/bin/env python3
"""Analyze an Isaac Sim ROS 2 dynamic-control bag.

The OpenArm timestamped bridge records the original command header in the
receipt's ``velocity`` field as ``[source_sec, source_nanosec]``.  This makes
command-to-receipt latency measurable even if the short-lived command publisher
was not discovered by rosbag before it sent its one message.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


NSEC = 1_000_000_000


def header_ns(message) -> int:
    return int(message.header.stamp.sec) * NSEC + int(message.header.stamp.nanosec)


def message_dict(message) -> dict:
    return {
        "header_ns": header_ns(message),
        "names": list(message.name),
        "position": [float(x) for x in message.position],
        "velocity": [float(x) for x in message.velocity],
    }


def source_ns(receipt: dict) -> int | None:
    velocity = receipt["velocity"]
    if len(velocity) != 2:
        return None
    seconds, nanoseconds = velocity
    if seconds < 1_000_000_000 or nanoseconds < 0 or nanoseconds >= NSEC:
        return None
    return int(seconds) * NSEC + int(nanoseconds)


def find_state_response(states: list[dict], receipt: dict) -> dict:
    target = dict(zip(receipt["names"], receipt["position"]))
    source = source_ns(receipt)
    receipt_time = receipt["header_ns"]
    before = [s for s in states if s["header_ns"] <= receipt_time]
    after = [s for s in states if s["header_ns"] >= receipt_time]

    result = {
        "source_timestamp_available": source is not None,
        "first_state_after_receipt_s": None,
        "first_state_after_command_s": None,
        "target_tolerance_reached_s": None,
        "target_tolerance_rad": None,
        "initial_abs_error_rad": {},
        "final_abs_error_rad": {},
    }
    if not after:
        return result

    first = after[0]
    result["first_state_after_receipt_s"] = (first["header_ns"] - receipt_time) / NSEC
    if source is not None:
        result["first_state_after_command_s"] = (first["header_ns"] - source) / NSEC

    baseline = before[-1] if before else first
    baseline_pos = dict(zip(baseline["names"], baseline["position"]))
    initial_error = {name: abs(baseline_pos.get(name, float("nan")) - value) for name, value in target.items()}
    result["initial_abs_error_rad"] = initial_error

    # 10% of the initial step, at least 0.002 rad, measured across all commanded joints.
    finite_initial = [x for x in initial_error.values() if x == x]
    tolerance = max(0.002, 0.1 * max(finite_initial, default=0.0))
    result["target_tolerance_rad"] = tolerance

    for state in after:
        actual = dict(zip(state["names"], state["position"]))
        errors = {name: abs(actual.get(name, float("nan")) - value) for name, value in target.items()}
        if all(error == error and error <= tolerance for error in errors.values()):
            anchor = source if source is not None else receipt_time
            result["target_tolerance_reached_s"] = (state["header_ns"] - anchor) / NSEC
            break

    last = after[-1]
    last_pos = dict(zip(last["names"], last["position"]))
    result["final_abs_error_rad"] = {
        name: abs(last_pos.get(name, float("nan")) - value) for name, value in target.items()
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bag", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(args.bag), storage_id="mcap"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    types = {item.name: item.type for item in reader.get_all_topics_and_types()}

    records = {name: [] for name in types}
    while reader.has_next():
        topic, raw, _bag_time = reader.read_next()
        message_type = get_message(types[topic])
        records[topic].append(message_dict(deserialize_message(raw, message_type)))

    command_topic = "/sim/openarm/timestamped_joint_command"
    receipt_topic = "/sim/openarm/command_receipt"
    state_topic = "/sim/openarm/joint_states"
    commands = records.get(command_topic, [])
    receipts = records.get(receipt_topic, [])
    states = records.get(state_topic, [])

    response = find_state_response(states, receipts[0]) if receipts else None
    latencies = []
    for receipt in receipts:
        source = source_ns(receipt)
        if source is not None:
            latencies.append((receipt["header_ns"] - source) / NSEC)

    result = {
        "source": "isaac_sim",
        "bag": str(args.bag),
        "topic_message_counts": {
            "timestamped_joint_command": len(commands),
            "command_receipt": len(receipts),
            "joint_states": len(states),
        },
        "command_recording": (
            "recorded" if commands else
            "not_recorded: command timestamp recovered from command_receipt.velocity"
        ),
        "command_to_receipt_latency_s": {
            "samples": len(latencies),
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
            "mean": sum(latencies) / len(latencies) if latencies else None,
        },
        "state_response": response,
        "acceptance": {
            "receipt_present": bool(receipts),
            "state_present": bool(states),
            "full_command_message_recorded": bool(commands),
            "closed_loop_evidence": bool(receipts and states),
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
