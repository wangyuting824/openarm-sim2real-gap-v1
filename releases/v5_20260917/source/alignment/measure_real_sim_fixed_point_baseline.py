#!/usr/bin/python3
"""Record one guarded real+Isaac fixed-point single-joint baseline trial.

The router owns physical publication.  It must have been started with an
explicit authorization ID, ``enable_real:=true``, ``real_publish_hz:=50`` and
``max_delta_rad`` no smaller than this trial's checked excursion.

This script publishes only two canonical partial commands: the selected joint
to an absolute target, then the measured real start position.  The router
continuously holds each accepted full real-arm target at the configured rate.
"""
import argparse
import json
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String


class BaselineTrial(Node):
    def __init__(self, joint):
        super().__init__("openarm_real_sim_fixed_point_baseline")
        self.joint = joint
        self.real, self.sim, self.receipts = [], [], []
        self.pub = self.create_publisher(JointState, "/openarm/command", 10)
        self.create_subscription(JointState, "/joint_states", self._on_real, 100)
        self.create_subscription(JointState, "/sim/openarm/joint_states_v2", self._on_sim, 100)
        self.create_subscription(String, "/openarm/dual_command_receipt", self._on_receipt, 100)

    def _append(self, message, output):
        values = dict(zip(message.name, message.position))
        if self.joint in values:
            output.append({"t_monotonic": time.monotonic(), "position_rad": float(values[self.joint])})

    def _on_real(self, message):
        self._append(message, self.real)

    def _on_sim(self, message):
        self._append(message, self.sim)

    def _on_receipt(self, message):
        try:
            self.receipts.append({"t_monotonic": time.monotonic(), **json.loads(message.data)})
        except json.JSONDecodeError:
            self.receipts.append({"t_monotonic": time.monotonic(), "raw": message.data})

    def spin_for(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.05)

    def command(self, target):
        command = JointState()
        command.header.stamp = self.get_clock().now().to_msg()
        command.name = [self.joint]
        command.position = [float(target)]
        self.pub.publish(command)


def last_after(samples, start):
    values = [sample["position_rad"] for sample in samples if sample["t_monotonic"] >= start]
    return values[-1] if values else None


def error(final, target):
    return None if final is None else final - target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--joint", required=True)
    parser.add_argument("--target-rad", type=float, default=0.1)
    parser.add_argument("--max-excursion-rad", type=float, default=0.15)
    parser.add_argument("--hold-s", type=float, default=3.0)
    parser.add_argument("--return-hold-s", type=float, default=1.0)
    parser.add_argument("--preflight-s", type=float, default=3.0)
    parser.add_argument("--sim-tolerance-rad", type=float, default=0.01)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.max_excursion_rad <= 0.0 or args.hold_s <= 0.0 or args.return_hold_s <= 0.0:
        raise ValueError("excursion and hold durations must be positive")

    rclpy.init()
    trial = BaselineTrial(args.joint)
    try:
        trial.spin_for(args.preflight_s)
        if not trial.real or not trial.sim:
            raise RuntimeError("missing real or simulation state before command")
        initial_real = trial.real[-1]["position_rad"]
        initial_sim = trial.sim[-1]["position_rad"]
        requested_excursion = args.target_rad - initial_real
        if abs(requested_excursion) > args.max_excursion_rad:
            raise RuntimeError(
                "target excursion %.6f rad exceeds %.6f rad" %
                (requested_excursion, args.max_excursion_rad)
            )

        outbound_start = time.monotonic()
        trial.command(args.target_rad)
        trial.spin_for(args.hold_s)
        outbound_real = last_after(trial.real, outbound_start)
        outbound_sim = last_after(trial.sim, outbound_start)

        return_start = time.monotonic()
        trial.command(initial_real)
        trial.spin_for(args.return_hold_s)
        return_real = last_after(trial.real, return_start)
        return_sim = last_after(trial.sim, return_start)
        sim_target_error = error(outbound_sim, args.target_rad)
        sim_target_tracking_passed = (
            sim_target_error is not None and abs(sim_target_error) <= args.sim_tolerance_rad
        )
        sim_return_error = error(return_sim, initial_real)
        sim_return_tracking_passed = (
            sim_return_error is not None and abs(sim_return_error) <= args.sim_tolerance_rad
        )
        # A drive is accepted only after it reaches both the commanded target
        # and the declared return target.  A target-only pass can hide weak
        # damping, insufficient settle time, or a conflicting hold callback.
        sim_tracking_passed = sim_target_tracking_passed and sim_return_tracking_passed

        metrics = {
            "kind": "openarm_real_sim_fixed_point_baseline",
            "trial_id": args.trial_id,
            "joint": args.joint,
            "target_rad": args.target_rad,
            "initial_real_rad": initial_real,
            "initial_sim_rad": initial_sim,
            "requested_real_excursion_rad": requested_excursion,
            "max_excursion_rad": args.max_excursion_rad,
            "hold_s": args.hold_s,
            "return_hold_s": args.return_hold_s,
            "outbound_final_real_rad": outbound_real,
            "outbound_final_sim_rad": outbound_sim,
            "outbound_real_error_rad": error(outbound_real, args.target_rad),
            "outbound_sim_error_rad": sim_target_error,
            "sim_tolerance_rad": args.sim_tolerance_rad,
            "sim_target_tracking_passed": sim_target_tracking_passed,
            "sim_return_tracking_passed": sim_return_tracking_passed,
            "sim_tracking_passed": sim_tracking_passed,
            "real_minus_sim_at_target_rad": (
                None if outbound_real is None or outbound_sim is None else outbound_real - outbound_sim
            ),
            "return_target_rad": initial_real,
            "return_final_real_rad": return_real,
            "return_final_sim_rad": return_sim,
            "return_real_error_rad": error(return_real, initial_real),
            "return_sim_error_rad": sim_return_error,
            "router_receipts": trial.receipts,
            "real_samples": trial.real,
            "sim_samples": trial.sim,
        }
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        summary = {key: value for key, value in metrics.items()
                   if key not in ("router_receipts", "real_samples", "sim_samples")}
        print(json.dumps(summary, indent=2))
        if not sim_tracking_passed:
            raise SystemExit("simulation target or return tracking failed; aborting remaining physical axes")
    finally:
        trial.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
