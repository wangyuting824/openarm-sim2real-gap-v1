#!/usr/bin/env python3
"""Measure timestamped-command to receipt skew for independently sent arms."""
import argparse
import json
from pathlib import Path

import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message

NS = 1_000_000_000
COMMAND = "/sim/openarm/timestamped_joint_command"
RECEIPT = "/sim/openarm/command_receipt"


def stamp(msg):
    return int(msg.header.stamp.sec) * NS + int(msg.header.stamp.nanosec)


def unpack(msg):
    return {"t": stamp(msg), "name": list(msg.name), "position": [float(x) for x in msg.position],
            "source_ns": int(msg.velocity[0]) * NS + int(msg.velocity[1]) if len(msg.velocity) == 2 else None}


ap = argparse.ArgumentParser()
ap.add_argument("bag")
ap.add_argument("--output", required=True)
a = ap.parse_args()
reader = rosbag2_py.SequentialReader()
reader.open(rosbag2_py.StorageOptions(uri=a.bag, storage_id="mcap"), rosbag2_py.ConverterOptions("cdr", "cdr"))
types = {x.name: x.type for x in reader.get_all_topics_and_types()}
data = {COMMAND: [], RECEIPT: []}
while reader.has_next():
    topic, raw, _ = reader.read_next()
    if topic in data:
        data[topic].append(unpack(deserialize_message(raw, get_message(types[topic]))))

by_joint = {}
for receipt in data[RECEIPT]:
    if len(receipt["name"]) != 1:
        continue
    joint = receipt["name"][0]
    by_joint[joint] = {"receipt_time_ns": receipt["t"], "source_time_ns": receipt["source_ns"],
                      "command_to_receipt_s": (receipt["t"] - receipt["source_ns"]) / NS if receipt["source_ns"] else None}
joints = sorted(by_joint)
skew = None
if len(joints) == 2:
    skew = abs(by_joint[joints[0]]["receipt_time_ns"] - by_joint[joints[1]]["receipt_time_ns"]) / NS
out = {"source": "isaac_sim", "command_count": len(data[COMMAND]), "receipt_count": len(data[RECEIPT]),
       "receipt_by_joint": by_joint, "independent_receipt_skew_s": skew,
       "definition": "absolute difference between Isaac receipt timestamps for separately stamped arm commands"}
Path(a.output).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps(out, indent=2))
