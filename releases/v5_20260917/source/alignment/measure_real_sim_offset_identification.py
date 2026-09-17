#!/usr/bin/env python3
"""Guarded one-joint multilevel real/Isaac identification recorder.

The surrounding runner owns real-router startup and named authorization. This
program sends a bounded canonical sequence and records both feedback streams.
It sends the measured real start as a return command in ``finally``.
"""
import argparse
import json
import math
import time
from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String


class Trial(Node):
    def __init__(self, joint):
        super().__init__("openarm_real_sim_offset_identification")
        self.joint, self.real, self.sim, self.receipts = joint, [], [], []
        self.pub = self.create_publisher(JointState, "/openarm/command", 10)
        self.create_subscription(JointState, "/joint_states", self._state(self.real), 100)
        self.create_subscription(JointState, "/sim/openarm/joint_states_v2", self._state(self.sim), 100)
        self.create_subscription(String, "/openarm/dual_command_receipt", self._receipt, 100)

    def _state(self, output):
        def callback(message):
            values = dict(zip(message.name, message.position))
            if self.joint in values:
                output.append({"t_monotonic": time.monotonic(), "position_rad": float(values[self.joint])})
        return callback

    def _receipt(self, message):
        try:
            self.receipts.append({"t_monotonic": time.monotonic(), **json.loads(message.data)})
        except json.JSONDecodeError:
            self.receipts.append({"t_monotonic": time.monotonic(), "raw": message.data})

    def spin_for(self, seconds):
        until = time.monotonic() + seconds
        while time.monotonic() < until:
            rclpy.spin_once(self, timeout_sec=min(0.05, until - time.monotonic()))

    def command(self, target):
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name, message.position = [self.joint], [float(target)]
        self.pub.publish(message)

    @staticmethod
    def final_after(samples, start):
        values = [x["position_rad"] for x in samples if x["t_monotonic"] >= start]
        return values[-1] if values else None


def stepped_targets(current, target, max_step):
    direction = 1.0 if target >= current else -1.0
    value = current
    while abs(target - value) > max_step:
        value += direction * max_step
        yield value
    yield target


def replay_target(calibration, joint, nominal, previous_nominal):
    """Mirror the Isaac bridge's v3 target transform for a tracking gate."""
    if calibration is None:
        return nominal, "nominal"
    entry = calibration["joints"].get(joint)
    if entry is None or not entry.get("enabled_for_isaac_replay", True):
        return nominal, "nominal"
    direction = "hold" if previous_nominal is None or nominal == previous_nominal else (
        "positive" if nominal > previous_nominal else "negative"
    )
    values = entry["emulation"]
    return (values["a"] * nominal + values["b_rad"] +
            values["h_%s_rad" % direction]), "emulated_" + direction


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--joint", required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--hold-s", type=float, default=3.0)
    parser.add_argument("--preflight-s", type=float, default=3.0)
    parser.add_argument("--preflight-attempts", type=int, default=3,
                        help="State-discovery attempts before any command (default: 3).")
    parser.add_argument("--max-excursion-rad", type=float, default=0.15)
    parser.add_argument("--max-substep-rad", type=float, default=0.025)
    parser.add_argument("--sim-tolerance-rad", type=float, default=0.01)
    parser.add_argument("--sim-replay-calibration", type=Path,
                        help="Frozen v3 replay JSON. The Isaac tracking gate then uses its emulated target.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--relative-waypoints", default="0.05,0,-0.05,0,0.10,0")
    args = parser.parse_args()
    if args.repetitions != 3:
        raise ValueError("identification protocol requires exactly three repetitions")
    if not (0 < args.max_substep_rad <= 0.025):
        raise ValueError("max substep must be in (0, 0.025]")

    rclpy.init()
    node = Trial(args.joint)
    calibration = None
    if args.sim_replay_calibration is not None:
        calibration = json.loads(args.sim_replay_calibration.read_text(encoding="utf-8"))
        if calibration.get("kind") != "openarm_isaac_replay_calibration":
            raise ValueError("unexpected replay calibration kind")
    metrics = {"kind": "openarm_real_sim_offset_identification", "trial_id": args.trial_id,
               "joint": args.joint, "hold_s": args.hold_s, "repetitions": args.repetitions,
               "max_excursion_rad": args.max_excursion_rad, "max_substep_rad": args.max_substep_rad,
               "sim_replay_calibration": None if args.sim_replay_calibration is None else str(args.sim_replay_calibration),
               "waypoint_runs": [], "aborted": False, "abort_reason": None}
    start = None
    active = None
    try:
        if args.preflight_attempts < 1:
            raise ValueError("preflight attempts must be at least one")
        metrics["preflight_attempts"] = 0
        # DDS endpoint discovery can briefly miss one cross-host stream.  Retry
        # only while no command has been published; a failed final attempt still
        # blocks the joint before motion.
        for attempt in range(1, args.preflight_attempts + 1):
            node.spin_for(args.preflight_s)
            metrics["preflight_attempts"] = attempt
            if node.real and node.sim:
                break
        if not node.real or not node.sim:
            raise RuntimeError("missing real or simulation state before command")
        start = node.real[-1]["position_rad"]
        active = start
        previous_nominal = None
        if args.preflight_only:
            metrics["preflight_passed"] = True
            metrics["passed"] = True
            return
        sequence = [float(x) for x in args.relative_waypoints.split(",")]
        if not sequence or sequence[-1] != 0.0:
            raise ValueError("relative waypoints must end at measured start (0.0)")
        for repetition in range(1, args.repetitions + 1):
            for relative in sequence:
                target = start + relative
                sim_tracking_target, sim_target_mode = replay_target(
                    calibration, args.joint, target, previous_nominal
                )
                if abs(relative) > args.max_excursion_rad:
                    raise RuntimeError("configured waypoint exceeds maximum excursion")
                # Subtarget receipts arrive during the stepping loop.  Begin
                # this window before publication so accepted commands count.
                receipt_start = len(node.receipts)
                for subtarget in stepped_targets(active, target, args.max_substep_rad):
                    node.command(subtarget)
                    node.spin_for(0.05)
                active = target
                waypoint_start = time.monotonic()
                node.spin_for(args.hold_s)
                real_final = node.final_after(node.real, waypoint_start)
                sim_final = node.final_after(node.sim, waypoint_start)
                sim_error = None if sim_final is None else sim_final - sim_tracking_target
                accepted = [x for x in node.receipts[receipt_start:] if x.get("accepted")]
                run = {"repetition": repetition, "relative_target_rad": relative,
                       "target_rad": target, "start_monotonic": waypoint_start,
                       "final_real_rad": real_final, "final_sim_rad": sim_final,
                       "real_error_rad": None if real_final is None else real_final - target,
                       "sim_nominal_target_rad": target,
                       "sim_tracking_target_rad": sim_tracking_target,
                       "sim_tracking_target_mode": sim_target_mode,
                       "sim_error_rad": sim_error, "accepted_receipts": len(accepted)}
                metrics["waypoint_runs"].append(run)
                if not accepted:
                    raise RuntimeError("no accepted router receipt at %.3f rad" % relative)
                if sim_error is None or abs(sim_error) > args.sim_tolerance_rad:
                    raise RuntimeError("simulation tracking gate failed at %.3f rad: %r" % (relative, sim_error))
                previous_nominal = target
        metrics["passed"] = True
    except Exception as error:
        metrics["aborted"] = True
        metrics["abort_reason"] = repr(error)
        metrics["passed"] = False
        raise
    finally:
        if start is not None and active is not None and not args.preflight_only:
            # Bounded return is issued even after a gate failure; router maintains it at 50 Hz.
            try:
                for subtarget in stepped_targets(active, start, args.max_substep_rad):
                    node.command(subtarget)
                    node.spin_for(0.05)
                node.spin_for(args.hold_s)
            except Exception as return_error:
                metrics["return_error"] = repr(return_error)
        metrics["initial_real_rad"] = start
        metrics["router_receipts"] = node.receipts
        metrics["real_samples"] = node.real
        metrics["sim_samples"] = node.sim
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
