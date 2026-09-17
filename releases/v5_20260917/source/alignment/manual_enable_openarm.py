#!/usr/bin/env python3
"""Manually enable one or two OpenArm arm buses without commanding motion.

This is a recovery/diagnostic utility.  It sends only Damiao enable packets and
reads feedback; it does not publish ROS messages and never sends a position,
velocity, torque, zeroing, or return-to-home command.

Run it only after stopping ros2_control_node.  Two CAN writers can otherwise
interleave packets on the same bus, which is unsafe and makes diagnosis
meaningless.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

import openarm_can as oa


MOTOR_TYPES = [
    oa.MotorType.DM8009, oa.MotorType.DM8009,
    oa.MotorType.DM4340, oa.MotorType.DM4340,
    oa.MotorType.DM4310, oa.MotorType.DM4310, oa.MotorType.DM4310,
]
SEND_IDS = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07]
RECV_IDS = [0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17]


def active_ros2_control() -> str:
    result = subprocess.run(
        ["pgrep", "-af", "ros2_control_node"], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    return result.stdout.strip()


def enable_bus(can_name: str, samples: int, heartbeat_hz: float) -> None:
    arm = oa.OpenArm(can_name, True)  # The deployed bimanual launch uses CAN-FD.
    arm.init_arm_motors(MOTOR_TYPES, SEND_IDS, RECV_IDS)
    arm.set_callback_mode_all(oa.CallbackMode.STATE)
    period_s = 1.0 / heartbeat_hz
    print(f"ENABLE_HEARTBEAT_START can={can_name} joints=1..7 hz={heartbeat_hz:.1f} (not proof of motor power)")
    for _ in range(samples):
        # This diagnostic repeats only the deployed enable frame. It never
        # sends position, velocity, torque, zeroing, or return-to-home targets.
        arm.enable_all()
        arm.refresh_all()
        arm.recv_all(20_000)
        time.sleep(period_s)

    motors = arm.get_arm().get_motors()
    for index, motor in enumerate(motors, start=1):
        print(
            "FEEDBACK can=%s joint=%d local_enabled=%s position=%.6f velocity=%.6f torque=%.6f"
            % (can_name, index, motor.is_enabled(), motor.get_position(),
               motor.get_velocity(), motor.get_torque())
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--can", action="append", choices=("can0", "can1"), required=True,
        help="CAN-FD bus to enable; repeat for both arms (right=can0, left=can1).",
    )
    parser.add_argument("--samples", type=int, default=4,
                        help="Enable-heartbeat and feedback cycles (default: 4).")
    parser.add_argument("--heartbeat-hz", type=float, default=20.0,
                        help="Repeated enable-frame rate in Hz (default: 20).")
    parser.add_argument(
        "--confirm-ros2-control-stopped", action="store_true",
        help="Required acknowledgement that no ROS hardware controller owns the CAN bus.",
    )
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be at least 1")
    if not 1.0 <= args.heartbeat_hz <= 50.0:
        parser.error("heartbeat rate must be in [1, 50] Hz")
    if not args.confirm_ros2_control_stopped:
        parser.error("pass --confirm-ros2-control-stopped after stopping ros2_control_node")

    owner = active_ros2_control()
    if owner:
        print("REFUSED: ros2_control_node still owns CAN:\n" + owner, file=sys.stderr)
        print("Stop it first: tmux kill-session -t openarm_real_bringup", file=sys.stderr)
        return 2

    for can_name in dict.fromkeys(args.can):
        enable_bus(can_name, args.samples, args.heartbeat_hz)
    print("ENABLE_HEARTBEAT_COMPLETE: no position command was sent; verify CAN replies and physical green LEDs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
