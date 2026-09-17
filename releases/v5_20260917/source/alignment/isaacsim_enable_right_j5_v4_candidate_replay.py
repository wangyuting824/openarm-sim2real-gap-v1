"""Arm the Isaac-only R J5 v4 replay candidate for the next bridge reload.

This changes only the in-process Isaac bridge configuration.  It does not
publish a command, use a real ROS route, access CAN, or modify USD/URDF.
"""
import builtins

builtins._openarm_isaac_compensation_replay = True
builtins._openarm_isaac_compensation_config = (
    "/home/tangyuan/openarm_ws/alignment/calibrations/"
    "openarm_isaac_replay_calibration_v4_candidate_right_j5.json"
)
print("OPENARM_COMPENSATED_REPLAY_ENABLED calibration=v4_candidate_right_j5 "
      "reload_bridge_required=true scope=isaac_only")
