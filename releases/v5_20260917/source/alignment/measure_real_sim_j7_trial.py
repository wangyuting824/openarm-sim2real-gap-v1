#!/usr/bin/python3
"""Execute one explicitly authorized OpenArm+Isaac paired J7 step and record it."""
import argparse
import json
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String


class Trial(Node):
    def __init__(self, joint):
        super().__init__("openarm_real_sim_j7_trial_recorder")
        self.joint = joint
        self.real, self.sim = [], []
        self.router_receipts, self.sim_receipts = [], []
        self.pub = self.create_publisher(JointState, "/openarm/command", 10)
        self.create_subscription(JointState, "/joint_states", self._real, 100)
        self.create_subscription(JointState, "/sim/openarm/joint_states_v2", self._sim, 100)
        self.create_subscription(String, "/openarm/dual_command_receipt", self._router, 20)
        self.create_subscription(JointState, "/sim/openarm/command_receipt", self._sim_receipt, 20)

    def _state(self, message, store):
        values = dict(zip(message.name, message.position))
        if self.joint in values:
            store.append({"t_monotonic": time.monotonic(), "position_rad": float(values[self.joint])})

    def _real(self, message): self._state(message, self.real)
    def _sim(self, message): self._state(message, self.sim)

    def _router(self, message):
        try:
            self.router_receipts.append({"t_monotonic": time.monotonic(), **json.loads(message.data)})
        except json.JSONDecodeError:
            self.router_receipts.append({"t_monotonic": time.monotonic(), "raw": message.data})

    def _sim_receipt(self, message):
        self.sim_receipts.append({
            "t_monotonic": time.monotonic(),
            "names": list(message.name), "positions": list(message.position),
        })

    def spin_for(self, duration):
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)

    def publish(self, position):
        command = JointState()
        command.header.stamp = self.get_clock().now().to_msg()
        command.name = [self.joint]
        command.position = [float(position)]
        self.pub.publish(command)


def last_after(samples, start, end=None):
    selected = [sample for sample in samples if sample["t_monotonic"] >= start and (end is None or sample["t_monotonic"] < end)]
    return selected[-1]["position_rad"] if selected else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--joint", default="openarm_right_joint7")
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument("--target-rad", type=float,
                              help="Absolute canonical joint target in radians.")
    target_group.add_argument("--target-delta-rad", type=float,
                              help="Offset from the measured real joint state in radians.")
    parser.add_argument("--return-rad", type=float,
                        help="Absolute return target; default is the measured initial real position.")
    parser.add_argument("--preflight-s", type=float, default=3.0,
                        help="DDS discovery/state collection time before any command (default: 3).")
    parser.add_argument("--preflight-only", action="store_true",
                        help="Validate dual state visibility and exit without publishing a command.")
    parser.add_argument("--hold-s", type=float, default=3.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rclpy.init()
    trial = Trial(args.joint)
    target_start = return_start = None
    try:
        trial.spin_for(args.preflight_s)
        if not trial.real or not trial.sim:
            raise RuntimeError("missing real or sim state before command")
        initial_real, initial_sim = trial.real[-1]["position_rad"], trial.sim[-1]["position_rad"]
        if args.preflight_only:
            print(json.dumps({
                "preflight_only": True,
                "joint": args.joint,
                "real_sample_count": len(trial.real),
                "sim_sample_count": len(trial.sim),
                "initial_real_rad": initial_real,
                "initial_sim_rad": initial_sim,
            }, indent=2))
            return
        if args.target_delta_rad is not None:
            target_rad = initial_real + args.target_delta_rad
        elif args.target_rad is not None:
            target_rad = args.target_rad
        else:
            raise RuntimeError("one of --target-rad or --target-delta-rad is required")
        return_rad = initial_real if args.return_rad is None else args.return_rad
        target_start = time.monotonic()
        trial.publish(target_rad)
        trial.spin_for(args.hold_s)
        return_start = time.monotonic()
        trial.publish(return_rad)
        trial.spin_for(args.hold_s)
    finally:
        # The authorized trial always attempts the defined return target, even
        # if recorder analysis or a subscription fails after the first command.
        if target_start is not None and return_start is None:
            trial.publish(return_rad)
            trial.spin_for(1.0)

    target_real = last_after(trial.real, target_start, return_start)
    target_sim = last_after(trial.sim, target_start, return_start)
    return_real = last_after(trial.real, return_start)
    return_sim = last_after(trial.sim, return_start)
    paired = [r for r in trial.router_receipts if r.get("sim_sent") and r.get("real_sent")]
    result = {
        "trial_id": args.trial_id, "joint": args.joint,
        "target_rad": target_rad, "target_delta_rad": args.target_delta_rad,
        "return_rad": return_rad, "hold_s": args.hold_s,
        "initial_real_rad": initial_real, "initial_sim_rad": initial_sim,
        "post_target_real_rad": target_real, "post_target_sim_rad": target_sim,
        "post_return_real_rad": return_real, "post_return_sim_rad": return_sim,
        "target_real_error_rad": None if target_real is None else target_real - target_rad,
        "target_sim_error_rad": None if target_sim is None else target_sim - target_rad,
        "target_real_sim_offset_rad": None if target_real is None or target_sim is None else target_real - target_sim,
        "return_real_error_rad": None if return_real is None else return_real - return_rad,
        "return_sim_error_rad": None if return_sim is None else return_sim - return_rad,
        "paired_router_receipt_count": len(paired),
        "router_receipts": trial.router_receipts,
        "sim_receipts": trial.sim_receipts,
        "real_samples": trial.real,
        "sim_samples": trial.sim,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ("router_receipts", "sim_receipts", "real_samples", "sim_samples")}, indent=2))
    if len(paired) != 2:
        raise SystemExit("OPENARM_REAL_SIM_TRIAL=FAIL router receipt count")
    print("OPENARM_REAL_SIM_TRIAL=COMPLETE")
    trial.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
