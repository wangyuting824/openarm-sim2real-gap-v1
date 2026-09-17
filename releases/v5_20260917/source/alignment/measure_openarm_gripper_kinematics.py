#!/usr/bin/env python3
"""Interactive, guarded no-load calibration for OpenArm pinch grippers.

The companion shell runner owns the named real authorization and starts the
single dual-target router.  This program never commands arm joints: it sends
one named finger joint at a time, records real/Isaac feedback and asks the
operator for a caliper width at each settled point.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String

ARM_JOINTS = [f"openarm_{side}_joint{i}" for side in ("left", "right") for i in range(1, 8)]
SIDES = {
    "left": ("openarm_left_finger_joint1", [0.08, 0.24, 0.40, 0.56, 0.70, 0.56, 0.40, 0.24, 0.08]),
    "right": ("openarm_right_finger_joint1", [-0.08, -0.24, -0.40, -0.56, -0.70, -0.56, -0.40, -0.24, -0.08]),
}


class Scan(Node):
    def __init__(self, joint: str):
        super().__init__("openarm_gripper_kinematic_scan")
        self.joint = joint
        self.real, self.sim, self.receipts = [], [], []
        self.latest_real = {}
        self.latest_sim = {}
        self.last_real_t = None
        self.last_sim_t = None
        self.pub = self.create_publisher(JointState, "/openarm/command", 10)
        self.create_subscription(JointState, "/joint_states", self._real, 100)
        self.create_subscription(JointState, "/sim/openarm/joint_states_v2", self._sim, 100)
        self.create_subscription(String, "/openarm/dual_command_receipt", self._receipt, 100)

    def _real(self, msg: JointState) -> None:
        self.latest_real.update({n: float(v) for n, v in zip(msg.name, msg.position)})
        self.last_real_t = time.monotonic()
        if self.joint in self.latest_real:
            self.real.append({"t_monotonic": self.last_real_t, "position_rad": self.latest_real[self.joint]})

    def _sim(self, msg: JointState) -> None:
        self.latest_sim.update({n: float(v) for n, v in zip(msg.name, msg.position)})
        self.last_sim_t = time.monotonic()
        if self.joint in self.latest_sim:
            self.sim.append({"t_monotonic": self.last_sim_t, "position_rad": self.latest_sim[self.joint]})

    def _receipt(self, msg: String) -> None:
        try:
            self.receipts.append({"t_monotonic": time.monotonic(), **json.loads(msg.data)})
        except json.JSONDecodeError:
            self.receipts.append({"t_monotonic": time.monotonic(), "raw": msg.data})

    def spin_for(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=min(0.05, deadline - time.monotonic()))

    def command(self, target: float) -> None:
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name, msg.position = [self.joint], [float(target)]
        self.pub.publish(msg)


def stepped(current: float, target: float, maximum: float):
    sign = 1.0 if target >= current else -1.0
    while abs(target - current) > maximum:
        current += sign * maximum
        yield current
    yield target


def latest_after(samples, start):
    values = [x["position_rad"] for x in samples if x["t_monotonic"] >= start]
    return values[-1] if values else None


def parse_width() -> float | None:
    while True:
        raw = input("卡尺读数（mm；输入 s 停止，空行表示未测）: ").strip().lower()
        if raw == "s":
            raise RuntimeError("operator_stop")
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            print("请输入毫米数值、s 或直接回车。")
            continue
        if not math.isfinite(value) or value < 0.0 or value > 200.0:
            print("读数必须在 0 到 200 mm。")
            continue
        return value


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--trial-id", required=True)
    p.add_argument("--side", choices=tuple(SIDES), required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--hold-s", type=float, default=3.0)
    p.add_argument("--max-substep-rad", type=float, default=0.010)
    p.add_argument("--arm-zero-tolerance-rad", type=float, default=0.03)
    args = p.parse_args()
    if not (0.0 < args.max_substep_rad <= 0.025):
        raise ValueError("max substep must be in (0, 0.025]")
    joint, targets = SIDES[args.side]
    rclpy.init()
    node = Scan(joint)
    result = {"schema_version": 1, "kind": "openarm_gripper_kinematic_scan", "trial_id": args.trial_id,
              "side": args.side, "joint": joint, "readings": [], "passed": False, "aborted": False}
    start = current = None
    try:
        node.spin_for(5.0)
        missing = [n for n in ARM_JOINTS + [joint] if n not in node.latest_real]
        if missing or not node.latest_sim:
            raise RuntimeError("missing_state:" + ",".join(missing or ["sim"]))
        if time.monotonic() - node.last_real_t > 0.25 or time.monotonic() - node.last_sim_t > 0.5:
            raise RuntimeError("stale_state")
        nonzero = {n: v for n, v in node.latest_real.items() if n in ARM_JOINTS and abs(v) > args.arm_zero_tolerance_rad}
        if nonzero:
            raise RuntimeError("arms_not_at_zero:" + repr(nonzero))
        start = current = node.latest_real[joint]
        for idx, target in enumerate(targets):
            receipt_start = len(node.receipts)
            for subtarget in stepped(current, target, args.max_substep_rad):
                node.command(subtarget)
                node.spin_for(0.06)
            current = target
            settled_at = time.monotonic()
            node.spin_for(args.hold_s)
            if any(abs(node.latest_real.get(n, 0.0)) > args.arm_zero_tolerance_rad for n in ARM_JOINTS):
                raise RuntimeError("arm_left_zero_tolerance")
            accepted = [r for r in node.receipts[receipt_start:] if r.get("accepted") and r.get("real_sent")]
            if not accepted:
                raise RuntimeError("no_accepted_real_receipt")
            direction = "increasing" if idx == 0 or target > targets[idx - 1] else "decreasing"
            print(f"{args.side} point {idx + 1}/{len(targets)}: target={target:.4f} rad. 请测两指垫最小间距。")
            width = parse_width()
            result["readings"].append({"index": idx + 1, "direction": direction, "command_rad": target,
                                       "real_feedback_rad": latest_after(node.real, settled_at),
                                       "sim_feedback_rad": latest_after(node.sim, settled_at),
                                       "measured_opening_mm": width, "receipts": accepted})
        result["passed"] = all(x["measured_opening_mm"] is not None for x in result["readings"])
    except Exception as exc:
        result["aborted"] = True
        result["abort_reason"] = repr(exc)
        raise
    finally:
        if start is not None and current is not None:
            try:
                for subtarget in stepped(current, start, args.max_substep_rad):
                    node.command(subtarget)
                    node.spin_for(0.06)
                node.spin_for(args.hold_s)
                result["return_real_feedback_rad"] = node.latest_real.get(joint)
            except Exception as exc:
                result["return_error"] = repr(exc)
        result["initial_real_feedback_rad"] = start
        result["real_samples"] = node.real
        result["sim_samples"] = node.sim
        result["router_receipts"] = node.receipts
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
