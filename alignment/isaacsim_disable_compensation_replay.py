"""Disable candidate compensation for the next timestamped bridge reload."""
import builtins

builtins._openarm_isaac_compensation_replay = False
print("OPENARM_COMPENSATED_REPLAY_DISABLED reload_bridge_required=true")
