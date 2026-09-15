#!/usr/bin/python3
"""Read-only health check for the OpenArm real--Isaac Sim gap workflow.

Run this on the Isaac host inside its ROS 2 container.  It waits for one
message stream from the real robot and one from Isaac Sim, then writes a
small JSON evidence file.  It deliberately publishes no command.
"""
import argparse
import json
import os
import time
from dataclasses import dataclass, field

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


DEFAULT_MAPPING = os.path.join(os.path.dirname(__file__), "openarm_isaacsim_joint_map.json")


@dataclass
class Stream:
    topic: str
    count: int = 0
    names: list = field(default_factory=list)
    position_count: int = 0
    arrival_times: list = field(default_factory=list)
    last_header_stamp: dict | None = None

    def observe(self, message: JointState) -> None:
        self.count += 1
        self.names = list(message.name)
        self.position_count = len(message.position)
        self.arrival_times.append(time.monotonic())
        # Enough to calculate a stable short-window rate without retaining data.
        self.arrival_times = self.arrival_times[-200:]
        self.last_header_stamp = {
            "sec": int(message.header.stamp.sec),
            "nanosec": int(message.header.stamp.nanosec),
        }

    def report(self) -> dict:
        elapsed = self.arrival_times[-1] - self.arrival_times[0] if len(self.arrival_times) > 1 else 0.0
        hz = (len(self.arrival_times) - 1) / elapsed if elapsed > 0 else None
        return {
            "topic": self.topic,
            "received": self.count > 0,
            "message_count": self.count,
            "joint_name_count": len(self.names),
            "position_count": self.position_count,
            "mean_hz": hz,
            "last_header_stamp": self.last_header_stamp,
            "joint_names": self.names,
        }


class GapHealthAgent(Node):
    def __init__(self, real_topic: str, sim_topic: str) -> None:
        super().__init__("openarm_real_sim_gap_health_agent")
        self.real = Stream(real_topic)
        self.sim = Stream(sim_topic)
        self.create_subscription(JointState, real_topic, self.real.observe, 50)
        self.create_subscription(JointState, sim_topic, self.sim.observe, 50)


def validate_mapping(mapping_path: str, real_names: list, sim_names: list) -> dict:
    """Validate named comparison joints; no command is generated from this file."""
    with open(mapping_path, encoding="utf-8") as handle:
        mapping = json.load(handle)
    real_map = mapping.get("canonical_to_real", {})
    sim_map = mapping.get("canonical_to_sim", {})
    canonical_real, canonical_sim = set(real_map), set(sim_map)
    required = sorted(canonical_real | canonical_sim)
    missing_real_keys = sorted(canonical_sim - canonical_real)
    missing_sim_keys = sorted(canonical_real - canonical_sim)
    mapped_real, mapped_sim = list(real_map.values()), list(sim_map.values())
    missing_real_names = sorted(set(mapped_real) - set(real_names))
    missing_sim_names = sorted(set(mapped_sim) - set(sim_names))
    duplicate_real = sorted({name for name in mapped_real if mapped_real.count(name) > 1})
    duplicate_sim = sorted({name for name in mapped_sim if mapped_sim.count(name) > 1})
    allowed_sim_extra = set(mapping.get("sim_unmapped_dofs", []))
    unexpected_real = sorted(set(real_names) - set(mapped_real))
    unexpected_sim = sorted(set(sim_names) - set(mapped_sim) - allowed_sim_extra)
    valid = not any((missing_real_keys, missing_sim_keys, missing_real_names,
                     missing_sim_names, duplicate_real, duplicate_sim,
                     unexpected_real, unexpected_sim))
    return {
        "path": os.path.abspath(mapping_path),
        "version": mapping.get("version"),
        "canonical_joint_count": len(required),
        "valid": valid,
        "missing_real_keys": missing_real_keys,
        "missing_sim_keys": missing_sim_keys,
        "missing_real_names": missing_real_names,
        "missing_sim_names": missing_sim_names,
        "duplicate_real_names": duplicate_real,
        "duplicate_sim_names": duplicate_sim,
        "unexpected_real_names": unexpected_real,
        "unexpected_sim_names": unexpected_sim,
        "declared_sim_unmapped_dofs": sorted(allowed_sim_extra),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only real/Isaac ROS health check")
    parser.add_argument("--duration-s", type=float, default=5.0)
    parser.add_argument("--real-topic", default="/joint_states")
    parser.add_argument("--sim-topic", default="/sim/openarm/joint_states_v2")
    parser.add_argument("--sim-command-topic", default="/sim/openarm/timestamped_joint_command")
    parser.add_argument("--sim-receipt-topic", default="/sim/openarm/command_receipt")
    parser.add_argument("--mapping", default=DEFAULT_MAPPING)
    parser.add_argument("--output", default="real_sim_gap_health.json")
    args = parser.parse_args()
    if args.duration_s <= 0:
        parser.error("--duration-s must be positive")

    rclpy.init()
    agent = GapHealthAgent(args.real_topic, args.sim_topic)
    deadline = time.monotonic() + args.duration_s
    while time.monotonic() < deadline:
        rclpy.spin_once(agent, timeout_sec=min(0.2, deadline - time.monotonic()))

    real = agent.real.report()
    sim = agent.sim.report()
    mapping = validate_mapping(args.mapping, real["joint_names"], sim["joint_names"])
    topic_names = {name for name, _types in agent.get_topic_names_and_types()}
    state_ready = (
        real["received"] and sim["received"]
        and real["joint_name_count"] >= 16 and sim["joint_name_count"] >= 18
        and mapping["valid"]
    )
    command_route = {
        "sim_command_topic": args.sim_command_topic,
        "sim_command_endpoint_present": args.sim_command_topic in topic_names,
        "sim_receipt_topic": args.sim_receipt_topic,
        "sim_receipt_endpoint_present": args.sim_receipt_topic in topic_names,
    }
    result = {
        "kind": "openarm_real_isaac_gap_health",
        "wall_time_unix_s": time.time(),
        "duration_s": args.duration_s,
        "real": real,
        "sim": sim,
        "mapping": mapping,
        "command_route": command_route,
        "state_ready": state_ready,
        "ready_for_measurement": state_ready and all(command_route.values()),
        "safety": "read_only: this program publishes no command",
    }
    output = os.path.abspath(args.output)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("OPENARM_GAP_STATE=" + ("READY" if result["state_ready"] else "NOT_READY"))
    print("OPENARM_GAP_MEASUREMENT=" + ("READY" if result["ready_for_measurement"] else "NOT_READY"))
    print("evidence=" + output)
    agent.destroy_node()
    rclpy.shutdown()
    return 0 if result["ready_for_measurement"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
