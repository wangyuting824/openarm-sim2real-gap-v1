#!/usr/bin/env python3
"""Request and summarize the read-only Isaac R J5 drive diagnostic."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String
from std_srvs.srv import Trigger


SERVICE = "/openarm/isaac_gap/diagnose"
TOPIC = "/openarm/isaac_gap/diagnostic_json"
OUTPUT = Path("alignment/results/isaac_only_right_j5_v4_candidate/drive_diagnostic_latest.json")


def main():
    rclpy.init()
    node = rclpy.create_node("openarm_right_j5_readonly_diagnostic")
    qos = QoSProfile(depth=1)
    qos.durability = DurabilityPolicy.TRANSIENT_LOCAL
    qos.reliability = ReliabilityPolicy.RELIABLE
    received = []
    requested_at = None

    def callback(message):
        try:
            data = json.loads(message.data)
            created = data.get("created_at_utc")
            if requested_at is None or not isinstance(created, str):
                return
            try:
                created_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except ValueError:
                return
            if created_at >= requested_at:
                received.append(data)
        except json.JSONDecodeError as error:
            received.append({"parse_error": repr(error), "raw": message.data})

    node.create_subscription(String, TOPIC, callback, qos)
    client = node.create_client(Trigger, SERVICE)
    if not client.wait_for_service(timeout_sec=12.0):
        raise RuntimeError("Isaac diagnostic service unavailable: " + SERVICE)
    # The topic is transient-local and can immediately replay a previous
    # diagnostic.  Accept only a probe timestamped after this request.
    requested_at = datetime.now(timezone.utc)
    future = client.call_async(Trigger.Request())
    deadline = time.monotonic() + 12.0
    while not future.done() and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    if not future.done():
        raise RuntimeError("Isaac diagnostic service timed out")
    response = future.result()
    if not response.success:
        raise RuntimeError("Isaac diagnostic rejected: " + response.message)

    deadline = time.monotonic() + 12.0
    while not received and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    if not received:
        raise RuntimeError("Isaac diagnostic topic timed out: " + TOPIC)
    data = received[-1]
    articulation = data.get("articulation", {})
    names = articulation.get("dof_names", [])
    positions = articulation.get("joint_positions_rad", [])
    velocities = articulation.get("joint_velocities_rad_s", [])
    try:
        index = names.index("openarm_right_joint5")
        rj5_state = {
            "dof_index": index,
            "position_rad": positions[index] if index < len(positions) else None,
            "velocity_rad_s": velocities[index] if index < len(velocities) else None,
        }
    except ValueError:
        rj5_state = {"error": "openarm_right_joint5 absent from articulation dof_names"}
    rj5_drives = [
        item for item in data.get("angular_drives", [])
        if "right" in item.get("prim_path", "").lower()
        and ("joint5" in item.get("prim_path", "").lower() or "joint_5" in item.get("prim_path", "").lower())
    ]
    summary = {
        "kind": "openarm_isaac_right_j5_readonly_diagnostic",
        "read_only": True,
        "diagnostic_created_at_utc": data.get("created_at_utc"),
        "stage_root_layer": data.get("stage_root_layer"),
        "right_j5_state": rj5_state,
        "right_j5_drives": rj5_drives,
        "bridge": data.get("bridge"),
        "static_hold_present": data.get("static_hold_present"),
        "runtime_performance_settings": data.get("runtime_performance_settings"),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("OPENARM_RIGHT_J5_READONLY_DIAGNOSTIC=PASS output=" + str(OUTPUT))
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
