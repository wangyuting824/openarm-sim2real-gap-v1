"""Enable candidate compensation for the next timestamped bridge reload.

Isaac-only compare/replay mode.  It publishes no robot command by itself.
"""
import builtins

builtins._openarm_isaac_compensation_replay = True
builtins._openarm_isaac_compensation_config = (
    "/home/tangyuan/openarm_ws/alignment/calibrations/"
    "openarm_isaac_replay_calibration_v3.json"
)
print("OPENARM_COMPENSATED_REPLAY_ENABLED calibration=v3 reload_bridge_required=true")
