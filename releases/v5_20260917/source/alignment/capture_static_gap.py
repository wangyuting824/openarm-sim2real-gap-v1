#!/usr/bin/env python3
"""Capture a static sim/real joint-state window and summarize the gap.

Read-only: this script never publishes commands or calls ros2_control services.
"""
import argparse
import csv
import math
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class Capture(Node):
    def __init__(self, sim_topic, real_topic, duration, output, joint_prefix=None):
        super().__init__("static_gap_capture")
        self.duration = duration
        self.output = Path(output)
        self.joint_prefix = joint_prefix
        self.sim = None
        self.real = None
        self.rows = []
        self.start = None
        self.create_subscription(JointState, sim_topic, self.sim_cb, 20)
        self.create_subscription(JointState, real_topic, self.real_cb, 20)
        self.create_timer(0.02, self.tick)

    def sim_cb(self, msg):
        self.sim = msg

    def real_cb(self, msg):
        self.real = msg

    @staticmethod
    def values(msg):
        return dict(zip(msg.name, msg.position)) if msg else {}

    def tick(self):
        if self.sim is None or self.real is None:
            return
        sim = self.values(self.sim)
        real = self.values(self.real)
        names = sorted(set(sim) & set(real))
        if self.joint_prefix:
            names = [n for n in names if n.startswith(self.joint_prefix)]
        if not names:
            return
        now = time.time_ns()
        if self.start is None:
            self.start = now
            self.get_logger().info(f"Both JointState streams ready; capturing {self.duration:.1f} s")
        if (now - self.start) / 1e9 > self.duration:
            self.finish()
            return
        for name in names:
            s, r = float(sim[name]), float(real[name])
            self.rows.append((now, name, s, r, r - s))

    def finish(self):
        self.output.parent.mkdir(parents=True, exist_ok=True)
        sample_path = self.output.with_name(self.output.stem + "_samples.csv")
        summary_path = self.output.with_name(self.output.stem + "_summary.csv")
        with sample_path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["wall_time_ns", "joint", "sim_position_rad", "real_position_rad", "error_rad"])
            w.writerows(self.rows)
        grouped = {}
        for _, name, s, r, e in self.rows:
            grouped.setdefault(name, []).append((s, r, e))
        with summary_path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["joint", "samples", "mean_error_rad", "mean_error_deg", "rmse_rad", "rmse_deg", "std_rad", "max_abs_error_rad", "sim_mean_rad", "real_mean_rad"])
            for name in sorted(grouped):
                vals = grouped[name]
                errors = [x[2] for x in vals]
                mean = sum(errors) / len(errors)
                rmse = math.sqrt(sum(e * e for e in errors) / len(errors))
                std = math.sqrt(sum((e - mean) ** 2 for e in errors) / len(errors))
                w.writerow([name, len(errors), mean, math.degrees(mean), rmse, math.degrees(rmse), std, max(map(abs, errors)), sum(x[0] for x in vals) / len(vals), sum(x[1] for x in vals) / len(vals)])
        self.get_logger().info(f"Wrote {sample_path} and {summary_path}")
        rclpy.shutdown()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sim-topic", default="/sim/joint_states")
    p.add_argument("--real-topic", default="/joint_states")
    p.add_argument("--duration", type=float, default=5.0)
    p.add_argument("--output", default="alignment/results/right_left_static_gap")
    p.add_argument("--joint-prefix", default=None, help="Only save joints with this name prefix, e.g. openarm_left_")
    args = p.parse_args()
    rclpy.init()
    node = Capture(args.sim_topic, args.real_topic, args.duration, args.output, args.joint_prefix)
    rclpy.spin(node)


if __name__ == "__main__":
    main()
