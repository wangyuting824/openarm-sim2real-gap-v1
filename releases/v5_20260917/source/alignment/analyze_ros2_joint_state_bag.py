#!/usr/bin/env python3
"""Analyze an Isaac Sim ROS 2 JointState bag without making any control call.

Run this with the ROS Jazzy Python environment, normally inside
``openarm-sim-ros``.  It writes one row per joint and a compact JSON summary.
Every row contains the joint name, rather than relying on a fixed array order.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from rclpy.serialization import deserialize_message
from rosbag2_py import ConverterOptions, SequentialReader, StorageOptions
from rosidl_runtime_py.utilities import get_message


def _finite(values):
    return [float(value) for value in values if math.isfinite(float(value))]


def _stats(values):
    values = _finite(values)
    if not values:
        return {"count": 0, "mean": None, "std": None, "min": None, "max": None}
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "std": statistics.stdev(values) if len(values) >= 2 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bag", help="rosbag directory containing metadata.yaml")
    parser.add_argument("--topic", default="/sim/openarm/joint_states")
    parser.add_argument("--output", required=True, help="directory for metrics.json and joint_stats.csv")
    args = parser.parse_args()

    bag_dir = Path(args.bag).resolve()
    output = Path(args.output).resolve()
    if not (bag_dir / "metadata.yaml").is_file():
        raise SystemExit("metadata.yaml not found in " + str(bag_dir))
    output.mkdir(parents=True, exist_ok=True)

    reader = SequentialReader()
    reader.open(StorageOptions(uri=str(bag_dir), storage_id="mcap"), ConverterOptions("cdr", "cdr"))
    types = {item.name: item.type for item in reader.get_all_topics_and_types()}
    if args.topic not in types:
        raise SystemExit("topic not present: %s; available: %s" % (args.topic, sorted(types)))
    message_type = get_message(types[args.topic])

    position_by_name = defaultdict(list)
    velocity_by_name = defaultdict(list)
    message_times_ns = []
    bag_times_ns = []
    names_seen = []
    message_count = 0

    while reader.has_next():
        topic, raw, bag_time_ns = reader.read_next()
        if topic != args.topic:
            continue
        message = deserialize_message(raw, message_type)
        message_count += 1
        bag_times_ns.append(int(bag_time_ns))
        header_ns = int(message.header.stamp.sec) * 1_000_000_000 + int(message.header.stamp.nanosec)
        message_times_ns.append(header_ns if header_ns > 0 else int(bag_time_ns))
        for index, name in enumerate(message.name):
            if name not in names_seen:
                names_seen.append(name)
            if index < len(message.position):
                position_by_name[name].append(message.position[index])
            if index < len(message.velocity):
                velocity_by_name[name].append(message.velocity[index])

    if message_count == 0:
        raise SystemExit("no messages read from " + args.topic)

    ordered_times = sorted(set(message_times_ns))
    dt_s = [(later - earlier) / 1e9 for earlier, later in zip(ordered_times, ordered_times[1:]) if later > earlier]
    frequency = _stats([1.0 / value for value in dt_s if value > 0.0])
    summary = {
        "source": "isaac_sim",
        "topic": args.topic,
        "bag": str(bag_dir),
        "message_count": message_count,
        "header_duration_s": (max(message_times_ns) - min(message_times_ns)) / 1e9 if len(message_times_ns) > 1 else 0.0,
        "state_frequency_hz": frequency,
        "joint_names_in_first_seen_order": names_seen,
        "joint_count": len(names_seen),
        "effort": "not_available: publisher emitted no effort array",
        "per_joint": {},
    }
    for name in names_seen:
        summary["per_joint"][name] = {
            "position_rad": _stats(position_by_name[name]),
            "velocity_rad_s": _stats(velocity_by_name[name]),
        }

    with (output / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    with (output / "joint_stats.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "joint_name", "position_count", "position_mean_rad", "position_std_rad",
            "position_min_rad", "position_max_rad", "velocity_count", "velocity_mean_rad_s",
            "velocity_std_rad_s", "velocity_min_rad_s", "velocity_max_rad_s",
        ])
        for name in names_seen:
            pos = summary["per_joint"][name]["position_rad"]
            vel = summary["per_joint"][name]["velocity_rad_s"]
            writer.writerow([
                name, pos["count"], pos["mean"], pos["std"], pos["min"], pos["max"],
                vel["count"], vel["mean"], vel["std"], vel["min"], vel["max"],
            ])
    print("OPENARM_BAG_ANALYZED messages=%d joints=%d output=%s" % (message_count, len(names_seen), output))


if __name__ == "__main__":
    main()
