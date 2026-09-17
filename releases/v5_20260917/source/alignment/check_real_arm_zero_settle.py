#!/usr/bin/env python3
"""Read-only gate: require all 14 real arm joints to remain near zero."""
import argparse
import json
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

ARM = [f"openarm_{side}_joint{i}" for side in ("left", "right") for i in range(1, 8)]


class Gate(Node):
    def __init__(self):
        super().__init__("openarm_zero_settle_gate")
        self.samples = []
        self.create_subscription(JointState, "/joint_states", self.cb, 50)

    def cb(self, msg):
        pos = dict(zip(msg.name, msg.position))
        if all(j in pos for j in ARM):
            self.samples.append({j: float(pos[j]) for j in ARM})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration-s", type=float, default=3.0)
    ap.add_argument("--tolerance-rad", type=float, default=.01)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    rclpy.init(); node = Gate(); end = time.monotonic() + args.duration_s
    while time.monotonic() < end: rclpy.spin_once(node, timeout_sec=.1)
    maxima = {j: max((abs(s[j]) for s in node.samples), default=float("inf")) for j in ARM}
    result = {"kind":"openarm_real_arm_zero_settle_gate","read_only":True,"sample_count":len(node.samples),
              "tolerance_rad":args.tolerance_rad,"max_abs_position_rad":maxima,
              "passed":bool(node.samples) and all(v <= args.tolerance_rad for v in maxima.values())}
    node.destroy_node(); rclpy.shutdown(); args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result["passed"] else 2)

if __name__ == "__main__": main()
