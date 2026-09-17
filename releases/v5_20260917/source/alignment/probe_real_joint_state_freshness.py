#!/usr/bin/env python3
"""Read-only /joint_states inter-arrival probe for router stale-gate diagnosis."""
import argparse
import json
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class Probe(Node):
    def __init__(self):
        super().__init__("openarm_real_joint_state_freshness_probe")
        self.arrivals = []
        self.last = None
        self.count = 0
        self.create_subscription(JointState, "/joint_states", self.cb, 50)

    def cb(self, _msg):
        now = time.monotonic()
        if self.last is not None:
            self.arrivals.append(now - self.last)
        self.last = now
        self.count += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration-s", type=float, default=60.0)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    rclpy.init()
    node = Probe()
    end = time.monotonic() + args.duration_s
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.1)
    a = sorted(node.arrivals)
    q = lambda x: a[min(len(a) - 1, int(x * (len(a) - 1)))] if a else None
    result = {"kind": "openarm_real_joint_state_freshness_probe", "read_only": True,
              "duration_s": args.duration_s, "message_count": node.count,
              "interval_ms": {"median": None if not a else q(.5)*1000,
                              "p95": None if not a else q(.95)*1000,
                              "max": None if not a else max(a)*1000},
              "intervals_over_250ms": sum(x > .25 for x in a)}
    node.destroy_node(); rclpy.shutdown()
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
