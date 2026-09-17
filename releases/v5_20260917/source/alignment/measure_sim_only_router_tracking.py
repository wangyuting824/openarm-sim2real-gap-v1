#!/usr/bin/python3
"""Bounded simulation-only tracking check through /openarm/command.

The real target is never selected by this program.  It requires the router's
receipt to say `real_sent=false`, records Isaac feedback for a short target
and return sequence, then writes JSON evidence.
"""
import argparse
import json
import time
from pathlib import Path

import rclpy
from sensor_msgs.msg import JointState
from std_msgs.msg import String


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--joint", default="openarm_right_joint7")
    parser.add_argument("--target-rad", type=float, default=0.02)
    parser.add_argument("--hold-s", type=float, default=3.0)
    parser.add_argument("--tolerance-rad", type=float, default=0.01)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.hold_s <= 0 or args.tolerance_rad <= 0:
        parser.error("hold-s and tolerance-rad must be positive")

    samples, receipts = [], []
    rclpy.init()
    node = rclpy.create_node("openarm_sim_only_tracking_probe")
    publisher = node.create_publisher(JointState, "/openarm/command", 10)

    def state_callback(message):
        positions = dict(zip(message.name, message.position))
        if args.joint in positions:
            samples.append({"t_monotonic": time.monotonic(), "position": float(positions[args.joint])})

    def receipt_callback(message):
        try:
            receipts.append(json.loads(message.data))
        except json.JSONDecodeError:
            receipts.append({"raw": message.data})

    node.create_subscription(JointState, "/sim/openarm/joint_states_v2", state_callback, 50)
    node.create_subscription(String, "/openarm/dual_command_receipt", receipt_callback, 10)

    def spin_for(seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)

    def publish(target):
        message = JointState()
        message.name, message.position = [args.joint], [target]
        publisher.publish(message)

    spin_for(0.5)
    initial = samples[-1]["position"] if samples else None
    publish(args.target_rad)
    target_start = time.monotonic()
    spin_for(args.hold_s)
    target_samples = [sample for sample in samples if sample["t_monotonic"] >= target_start]
    target_final = target_samples[-1]["position"] if target_samples else None

    publish(0.0)
    return_start = time.monotonic()
    spin_for(args.hold_s)
    return_samples = [sample for sample in samples if sample["t_monotonic"] >= return_start]
    return_final = return_samples[-1]["position"] if return_samples else None

    sim_only = bool(receipts) and all(
        receipt.get("sim_sent") is True and receipt.get("real_sent") is False
        for receipt in receipts if "real_sent" in receipt
    )
    target_error = None if target_final is None else target_final - args.target_rad
    return_error = None if return_final is None else return_final
    passed = (
        sim_only and target_error is not None and return_error is not None
        and abs(target_error) <= args.tolerance_rad
        and abs(return_error) <= args.tolerance_rad
    )
    result = {
        "kind": "openarm_sim_only_router_tracking",
        "joint": args.joint,
        "target_rad": args.target_rad,
        "initial_rad": initial,
        "post_target_final_rad": target_final,
        "post_target_error_rad": target_error,
        "post_return_final_rad": return_final,
        "post_return_error_rad": return_error,
        "tolerance_rad": args.tolerance_rad,
        "all_receipts_sim_only": sim_only,
        "receipt_count": len(receipts),
        "sample_count": len(samples),
        "passed": passed,
        "samples": samples,
        "router_receipts": receipts,
    }
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in ("samples", "router_receipts")}, indent=2))
    print("OPENARM_SIM_ONLY_TRACKING=" + ("PASS" if passed else "FAIL"))
    node.destroy_node()
    rclpy.shutdown()
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
