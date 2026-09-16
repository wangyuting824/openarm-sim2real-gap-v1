#!/usr/bin/python3
"""Verify an Isaac-only compensated replay target through the sim-only route."""
import argparse
import json
import time
from pathlib import Path

import rclpy
from sensor_msgs.msg import JointState
from std_msgs.msg import String

from isaac_gap_compensation import CompensationModel


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--joint", default="openarm_right_joint5")
    parser.add_argument("--target-rad", type=float, default=0.02)
    parser.add_argument("--hold-s", type=float, default=3.0)
    parser.add_argument("--tolerance-rad", type=float, default=0.01)
    parser.add_argument("--discovery-timeout-s", type=float, default=12.0,
                        help="Maximum wait for the temporary publisher to match the router.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.hold_s <= 0 or args.tolerance_rad <= 0 or args.discovery_timeout_s <= 0:
        parser.error("hold-s, tolerance-rad, and discovery-timeout-s must be positive")

    model = CompensationModel.from_path(args.config)
    expected_target = model.emulate(args.joint, args.target_rad)
    expected_return = model.emulate(args.joint, 0.0)
    samples, receipts = [], []
    rclpy.init()
    node = rclpy.create_node("openarm_compensated_replay_probe")
    publisher = node.create_publisher(JointState, "/openarm/command", 10)

    def state_callback(message):
        values = dict(zip(message.name, message.position))
        if args.joint in values:
            samples.append({"t_monotonic": time.monotonic(), "position": float(values[args.joint])})

    def receipt_callback(message):
        try:
            receipts.append(json.loads(message.data))
        except json.JSONDecodeError:
            receipts.append({"raw": message.data})

    node.create_subscription(JointState, "/sim/openarm/joint_states_v2", state_callback, 50)
    node.create_subscription(String, "/openarm/dual_command_receipt", receipt_callback, 10)

    def spin_for(seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            rclpy.spin_once(node, timeout_sec=0.05)

    def publish(position):
        message = JointState()
        message.name, message.position = [args.joint], [position]
        publisher.publish(message)

    # A transient publisher can otherwise lose its first command while DDS is
    # still matching it to the long-running router.  This wait sends nothing.
    discovery_deadline = time.monotonic() + args.discovery_timeout_s
    while publisher.get_subscription_count() < 1 and time.monotonic() < discovery_deadline:
        spin_for(0.05)
    if publisher.get_subscription_count() < 1:
        raise RuntimeError("sim-only router subscriber was not discovered before command within %.1f s" % args.discovery_timeout_s)
    spin_for(0.25)
    receipt_before_target = len(receipts)
    publish(args.target_rad)
    target_start = time.monotonic()
    spin_for(args.hold_s)
    target_values = [x["position"] for x in samples if x["t_monotonic"] >= target_start]
    target_receipts = len(receipts) - receipt_before_target
    receipt_before_return = len(receipts)
    publish(0.0)
    return_start = time.monotonic()
    spin_for(args.hold_s)
    return_values = [x["position"] for x in samples if x["t_monotonic"] >= return_start]
    return_receipts = len(receipts) - receipt_before_return
    target_final = target_values[-1] if target_values else None
    return_final = return_values[-1] if return_values else None
    sim_only = bool(receipts) and all(x.get("sim_sent") is True and x.get("real_sent") is False
                                           for x in receipts if "real_sent" in x)
    target_error = None if target_final is None else target_final - expected_target["q_emulated_rad"]
    return_error = None if return_final is None else return_final - expected_return["q_emulated_rad"]
    passed = (sim_only and target_receipts >= 1 and return_receipts >= 1 and
              target_error is not None and return_error is not None and
              abs(target_error) <= args.tolerance_rad and abs(return_error) <= args.tolerance_rad)
    result = {"kind": "openarm_sim_only_compensated_replay", "joint": args.joint,
              "nominal_target_rad": args.target_rad, "expected_target": expected_target,
              "expected_return": expected_return, "target_final_rad": target_final,
              "return_final_rad": return_final, "target_error_rad": target_error,
              "return_error_rad": return_error, "tolerance_rad": args.tolerance_rad,
              "all_receipts_sim_only": sim_only, "receipt_count": len(receipts),
              "target_receipt_count": target_receipts, "return_receipt_count": return_receipts,
              "discovery_timeout_s": args.discovery_timeout_s,
              "sample_count": len(samples), "passed": passed, "samples": samples,
              "router_receipts": receipts}
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("samples", "router_receipts")}, indent=2))
    print("OPENARM_SIM_ONLY_COMPENSATED_REPLAY=" + ("PASS" if passed else "FAIL"))
    node.destroy_node()
    rclpy.shutdown()
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
