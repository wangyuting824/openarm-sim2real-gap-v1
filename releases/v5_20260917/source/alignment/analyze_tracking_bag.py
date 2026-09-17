#!/usr/bin/env python3
"""Compute per-command joint tracking values from the OpenArm ROS 2 bag."""

import argparse
import json
from pathlib import Path

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

NS = 1_000_000_000
COMMAND = "/sim/openarm/timestamped_joint_command"
RECEIPT = "/sim/openarm/command_receipt"
DEFAULT_STATE = "/sim/openarm/joint_states"


def ns(m):
    return int(m.header.stamp.sec) * NS + int(m.header.stamp.nanosec)


def unpack(m):
    return {"t": ns(m), "name": list(m.name), "position": [float(x) for x in m.position], "velocity": [float(x) for x in m.velocity]}


def source_time(receipt):
    if len(receipt["velocity"]) == 2:
        sec, nsec = receipt["velocity"]
        if sec >= 1_000_000_000 and 0 <= nsec < NS:
            return int(sec) * NS + int(nsec)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bag")
    ap.add_argument("--output", required=True)
    ap.add_argument("--tolerance-rad", type=float, default=0.002)
    ap.add_argument("--state-topic", default=DEFAULT_STATE)
    a = ap.parse_args()

    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=a.bag, storage_id="mcap"), rosbag2_py.ConverterOptions("cdr", "cdr"))
    types = {x.name: x.type for x in reader.get_all_topics_and_types()}
    data = {topic: [] for topic in types}
    while reader.has_next():
        topic, raw, _ = reader.read_next()
        data[topic].append(unpack(deserialize_message(raw, get_message(types[topic]))))

    receipts = data.get(RECEIPT, [])
    states = data.get(a.state_topic, [])
    rows = []
    for i, receipt in enumerate(receipts):
        source = source_time(receipt)
        begin, end = receipt["t"], receipts[i + 1]["t"] if i + 1 < len(receipts) else float("inf")
        before = [s for s in states if s["t"] <= begin]
        segment = [s for s in states if begin <= s["t"] < end]
        target = dict(zip(receipt["name"], receipt["position"]))
        baseline = dict(zip(before[-1]["name"], before[-1]["position"])) if before else {}
        initial = {n: abs(baseline.get(n, v) - v) for n, v in target.items()}
        reached = None
        final = {}
        for state in segment:
            actual = dict(zip(state["name"], state["position"]))
            errors = {n: abs(actual.get(n, v) - v) for n, v in target.items()}
            final = errors
            if reached is None and all(x <= a.tolerance_rad for x in errors.values()):
                reached = state["t"]
        rows.append({
            "command_index": i + 1,
            "target_rad": target,
            "command_to_receipt_s": (receipt["t"] - source) / NS if source else None,
            "receipt_to_first_state_s": (segment[0]["t"] - receipt["t"]) / NS if segment else None,
            "target_tolerance_rad": a.tolerance_rad,
            "initial_abs_error_rad": initial,
            "final_abs_error_rad": final,
            "command_to_tolerance_s": (reached - source) / NS if reached and source else None,
        })

    state_times = [s["t"] for s in states]
    intervals = [(state_times[i] - state_times[i - 1]) / NS for i in range(1, len(state_times)) if state_times[i] > state_times[i - 1]]
    out = {
        "source": "isaac_sim",
        "state_topic": a.state_topic,
        "topic_message_counts": {"command": len(data.get(COMMAND, [])), "receipt": len(receipts), "state": len(states)},
        "state_frequency_hz": sum(1 / x for x in intervals) / len(intervals) if intervals else None,
        "commands": rows,
        "limitations": (
            "Receipt velocity carries the original command timestamp."
            if len(data.get(COMMAND, [])) == len(receipts)
            else "Receipt velocity carries the original command timestamp; one or more raw commands are absent from this bag."
        ),
    }
    Path(a.output).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
