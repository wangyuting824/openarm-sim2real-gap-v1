#!/usr/bin/env python3
"""Record bounded paired step responses for OpenArm dynamic-gap fitting.

The router, not this recorder, owns physical publication.  Running this script
with a real-enabled router is a physical experiment and requires the named
authorization in its manifest.  It does not enable motors or start a router.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String


class DynamicRecorder(Node):
    def __init__(self, joint: str):
        super().__init__("openarm_real_sim_dynamic_identification")
        self.joint = joint
        self.real: list[dict] = []
        self.sim: list[dict] = []
        self.receipts: list[dict] = []
        self.isaac_timing: list[dict] = []
        self.publisher = self.create_publisher(JointState, "/openarm/command", 10)
        self.create_subscription(JointState, "/joint_states", self._on_real, 100)
        self.create_subscription(JointState, "/sim/openarm/joint_states_v2", self._on_sim, 100)
        self.create_subscription(String, "/openarm/dual_command_receipt", self._on_receipt, 100)
        self.create_subscription(String, "/openarm/isaac_gap/timing_json", self._on_timing, 100)

    def _append(self, message: JointState, destination: list[dict], *, simulator: bool) -> None:
        values = dict(zip(message.name, message.position))
        if self.joint in values:
            sample = {
                "t_monotonic": time.monotonic(),
                "ros_stamp_ns": int(message.header.stamp.sec) * 1_000_000_000 + int(message.header.stamp.nanosec),
                "position_rad": float(values[self.joint]),
            }
            if simulator:
                # The Isaac publisher stamps this simulator-only topic with
                # accumulated actual PhysX dt, never host wall time.
                sample["physics_time_s"] = sample["ros_stamp_ns"] / 1_000_000_000.0
            destination.append(sample)

    def _on_real(self, message: JointState) -> None:
        self._append(message, self.real, simulator=False)

    def _on_sim(self, message: JointState) -> None:
        self._append(message, self.sim, simulator=True)

    def _on_receipt(self, message: String) -> None:
        now = time.monotonic()
        try:
            self.receipts.append({"t_monotonic": now, **json.loads(message.data)})
        except json.JSONDecodeError:
            self.receipts.append({"t_monotonic": now, "raw": message.data})

    def _on_timing(self, message: String) -> None:
        try:
            self.isaac_timing.append({"received_t_monotonic": time.monotonic(), **json.loads(message.data)})
        except json.JSONDecodeError:
            self.isaac_timing.append({"received_t_monotonic": time.monotonic(), "raw": message.data})

    def spin_for(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)

    def publish(self, target: float) -> float:
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = [self.joint]
        message.position = [target]
        published_at = time.monotonic()
        self.publisher.publish(message)
        self.last_published_stamp_ns = int(message.header.stamp.sec) * 1_000_000_000 + int(message.header.stamp.nanosec)
        return published_at

    def wait_for_router(self, timeout_s: float = 12.0) -> None:
        deadline = time.monotonic() + timeout_s
        while self.publisher.get_subscription_count() < 1:
            if time.monotonic() >= deadline:
                raise RuntimeError("dynamic recorder router subscriber was not discovered before command")
            rclpy.spin_once(self, timeout_sec=0.05)


def latest(samples: list[dict]) -> float | None:
    return samples[-1]["position_rad"] if samples else None


def accepted_receipt_after(receipts: list[dict], start: float) -> dict | None:
    for receipt in receipts:
        if receipt["t_monotonic"] >= start and receipt.get("accepted") is True:
            return receipt
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--joint", required=True)
    parser.add_argument("--step-rad", type=float, nargs="+", default=[0.025, -0.025, 0.05, -0.05])
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--hold-s", type=float, default=2.0)
    parser.add_argument("--return-hold-s", type=float, default=2.0)
    parser.add_argument("--preflight-s", type=float, default=3.0)
    parser.add_argument("--max-excursion-rad", type=float, default=0.15)
    parser.add_argument("--require-real", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.repetitions < 3:
        raise ValueError("dynamic fitting requires at least three repetitions")
    if args.hold_s <= 0 or args.return_hold_s <= 0 or args.preflight_s <= 0:
        raise ValueError("all durations must be positive")
    if any(abs(step) > 0.05 for step in args.step_rad):
        raise ValueError("a dynamic step may not exceed 0.05 rad")

    rclpy.init()
    recorder = DynamicRecorder(args.joint)
    try:
        recorder.wait_for_router()
        recorder.spin_for(args.preflight_s)
        if not recorder.sim or (args.require_real and not recorder.real):
            raise RuntimeError("missing required state before command")
        reference = latest(recorder.real) if args.require_real else latest(recorder.sim)
        assert reference is not None
        events = []
        for repetition in range(1, args.repetitions + 1):
            for step in args.step_rad:
                target = reference + step
                if abs(target - reference) > args.max_excursion_rad:
                    raise RuntimeError("step exceeds declared excursion")
                start = recorder.publish(target)
                recorder.spin_for(args.hold_s)
                receipt = accepted_receipt_after(recorder.receipts, start)
                if receipt is None:
                    raise RuntimeError("no accepted router receipt for target step")
                events.append({
                    "kind": "step", "repetition": repetition, "step_rad": step,
                    "target_rad": target, "published_t_monotonic": start,
                    "published_ros_stamp_ns": recorder.last_published_stamp_ns,
                    "accepted_receipt_t_monotonic": receipt["t_monotonic"],
                    "hold_s": args.hold_s,
                })

                return_start = recorder.publish(reference)
                recorder.spin_for(args.return_hold_s)
                return_receipt = accepted_receipt_after(recorder.receipts, return_start)
                if return_receipt is None:
                    raise RuntimeError("no accepted router receipt for return")
                events.append({
                    "kind": "return", "repetition": repetition, "step_rad": 0.0,
                    "target_rad": reference, "published_t_monotonic": return_start,
                    "published_ros_stamp_ns": recorder.last_published_stamp_ns,
                    "accepted_receipt_t_monotonic": return_receipt["t_monotonic"],
                    "hold_s": args.return_hold_s,
                })

        payload = {
            "schema_version": 1,
            "kind": "openarm_real_sim_dynamic_identification_raw",
            "trial_id": args.trial_id,
            "joint": args.joint,
            "real_required": args.require_real,
            "static_replay_required": "disabled",
            "reference_rad": reference,
            "step_rad": args.step_rad,
            "repetitions": args.repetitions,
            "hold_s": args.hold_s,
            "return_hold_s": args.return_hold_s,
            "max_excursion_rad": args.max_excursion_rad,
            "events": events,
            "router_receipts": recorder.receipts,
            "isaac_timing": recorder.isaac_timing,
            "real_samples": recorder.real,
            "sim_samples": recorder.sim,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({
            "trial_id": args.trial_id, "joint": args.joint,
            "events": len(events), "accepted_receipts": len([r for r in recorder.receipts if r.get("accepted")]),
            "real_samples": len(recorder.real), "sim_samples": len(recorder.sim),
        }, indent=2))
        return 0
    finally:
        recorder.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
