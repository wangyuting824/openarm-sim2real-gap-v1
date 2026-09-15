#!/usr/bin/python3
"""Run an operator-authorized bounded streamed J7 real+Isaac trial.

The router must run with enable_real:=true, a matching authorization ID, and
real_publish_hz>0.  This runner only sends canonical partial JointState
commands; the router owns real-controller publication.
"""
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
        super().__init__("openarm_real_sim_streaming_j7_trial")
        self.joint = joint
        self.real, self.sim, self.receipts = [], [], []
        self.pub = self.create_publisher(JointState, "/openarm/command", 10)
        self.create_subscription(JointState, "/joint_states", self._real, 100)
        self.create_subscription(JointState, "/sim/openarm/joint_states_v2", self._sim, 100)
        self.create_subscription(String, "/openarm/dual_command_receipt", self._receipt, 100)

    def _state(self, message, output):
        values = dict(zip(message.name, message.position))
        if self.joint in values:
            output.append({"t_monotonic": time.monotonic(), "position_rad": float(values[self.joint])})

    def _real(self, message): self._state(message, self.real)
    def _sim(self, message): self._state(message, self.sim)

    def _receipt(self, message):
        try:
            self.receipts.append({"t_monotonic": time.monotonic(), **json.loads(message.data)})
        except json.JSONDecodeError:
            self.receipts.append({"t_monotonic": time.monotonic(), "raw": message.data})

    def spin_for(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=0.05)

    def command(self, target):
        message = JointState()
        message.header.stamp = self.get_clock().now().to_msg()
        message.name = [self.joint]
        message.position = [float(target)]
        self.pub.publish(message)


def final_after(samples, start):
    chosen = [x["position_rad"] for x in samples if x["t_monotonic"] >= start]
    return chosen[-1] if chosen else None


def run_leg(trial, endpoint, step_rad, stage_s, timeout_s, phase_log):
    """Approach endpoint by targets no farther than step_rad from live feedback."""
    started = time.monotonic()
    direction = 1.0 if endpoint >= trial.real[-1]["position_rad"] else -1.0
    while True:
        current = trial.real[-1]["position_rad"]
        remaining = endpoint - current
        if direction * remaining <= 0.003:
            target = endpoint
        else:
            target = current + direction * min(abs(remaining), step_rad)
        sent = time.monotonic()
        trial.command(target)
        phase_log.append({"t_monotonic": sent, "feedback_before_rad": current,
                          "target_rad": target})
        trial.spin_for(stage_s)
        if abs(endpoint - trial.real[-1]["position_rad"]) <= 0.006:
            if target == endpoint:
                return True
        if time.monotonic() - started > timeout_s:
            return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial-id", required=True)
    parser.add_argument("--joint", default="openarm_right_joint7")
    parser.add_argument("--delta-rad", type=float, default=0.1)
    parser.add_argument("--max-excursion-rad", type=float, default=0.15)
    parser.add_argument("--substep-rad", type=float, default=0.025)
    parser.add_argument("--stage-s", type=float, default=0.8)
    parser.add_argument("--hold-s", type=float, default=2.0)
    parser.add_argument("--leg-timeout-s", type=float, default=15.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not 0.0 < abs(args.delta_rad) <= args.max_excursion_rad:
        raise ValueError("delta-rad must be in (0, max-excursion-rad]")
    if not 0.0 < args.substep_rad <= args.max_excursion_rad:
        raise ValueError("substep-rad must be in (0, max-excursion-rad]")

    rclpy.init()
    trial = Trial(args.joint)
    try:
        trial.spin_for(3.0)
        if not trial.real or not trial.sim:
            raise RuntimeError("missing real or sim state before command")
        start = trial.real[-1]["position_rad"]
        endpoint = start + args.delta_rad
        outbound = []
        outbound_start = time.monotonic()
        reached_target = run_leg(trial, endpoint, args.substep_rad, args.stage_s,
                                 args.leg_timeout_s, outbound)
        trial.spin_for(args.hold_s)
        outbound_final_real = final_after(trial.real, outbound_start)
        outbound_final_sim = final_after(trial.sim, outbound_start)
        returning = []
        return_start = time.monotonic()
        returned = run_leg(trial, start, args.substep_rad, args.stage_s,
                           args.leg_timeout_s, returning)
        trial.spin_for(1.0)
        return_final_real = final_after(trial.real, return_start)
        return_final_sim = final_after(trial.sim, return_start)
        result = {
            "trial_id": args.trial_id, "joint": args.joint,
            "initial_real_rad": start, "requested_delta_rad": args.delta_rad,
            "endpoint_rad": endpoint, "max_excursion_rad": args.max_excursion_rad,
            "substep_rad": args.substep_rad, "stage_s": args.stage_s,
            "outbound_reached": reached_target, "outbound_final_real_rad": outbound_final_real,
            "outbound_final_sim_rad": outbound_final_sim,
            "outbound_real_error_rad": None if outbound_final_real is None else outbound_final_real - endpoint,
            "outbound_sim_error_rad": None if outbound_final_sim is None else outbound_final_sim - endpoint,
            "return_reached": returned, "return_final_real_rad": return_final_real,
            "return_final_sim_rad": return_final_sim,
            "return_real_error_rad": None if return_final_real is None else return_final_real - start,
            "return_sim_error_rad": None if return_final_sim is None else return_final_sim - start,
            "outbound_commands": outbound, "return_commands": returning,
            "router_receipts": trial.receipts, "real_samples": trial.real, "sim_samples": trial.sim,
        }
        output = Path(args.output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items()
                          if k not in ("outbound_commands", "return_commands", "router_receipts", "real_samples", "sim_samples")}, indent=2))
    finally:
        trial.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
