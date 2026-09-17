"""Hold the current OpenArm pose inside Isaac Sim for a valid static baseline.

This is a simulator-only position hold.  It never creates a ROS subscriber or
publisher and has no connection to the physical OpenArm.  It captures the
current articulation position once after PhysX initializes, then repeatedly
sends that same target to the Isaac articulation controller.
"""
from __future__ import annotations

import builtins

import omni.kit.app
import omni.timeline

ARTICULATION_ROOT = "/openarm_v20/Geometry/world/openarm_body_link0"


def _make_articulation():
    try:
        from isaacsim.core.prims import Articulation
        return Articulation(prim_paths_expr=ARTICULATION_ROOT, name="openarm_static_hold")
    except (ImportError, TypeError):
        from omni.isaac.core.articulations import Articulation
        return Articulation(prim_path=ARTICULATION_ROOT, name="openarm_static_hold")


def _make_action(target):
    try:
        from isaacsim.core.utils.types import ArticulationAction
    except ImportError:
        from omni.isaac.core.utils.types import ArticulationAction
    return ArticulationAction(joint_positions=target)


def main():
    old = getattr(builtins, "_openarm_static_hold", None)
    if old is not None:
        old["subscription"] = None
        print("Stopped previous OpenArm static hold.")

    timeline = omni.timeline.get_timeline_interface()
    timeline.play()
    state = {
        "articulation": _make_articulation(),
        "subscription": None,
        "initialized": False,
        "target": None,
        "controller": None,
        "printed_wait": False,
    }

    def on_update(_event):
        try:
            if not state["initialized"]:
                state["articulation"].initialize()
                # Isaac Sim 6's prim Articulation wrapper owns apply_action()
                # directly; it does not expose the legacy controller getter.
                state["controller"] = state["articulation"]
                target = state["articulation"].get_joint_positions()
                if hasattr(target, "copy"):
                    target = target.copy()
                state["target"] = target
                state["initialized"] = True
                print("OPENARM_STATIC_HOLD_ACTIVE dofs=%d" % len(state["articulation"].dof_names))
                print("Hold mode: simulator articulation position target each update; no ROS command input.")
            state["controller"].apply_action(_make_action(state["target"]))
        except Exception as error:
            if not state["printed_wait"]:
                print("OPENARM_STATIC_HOLD_WAITING " + repr(error))
                state["printed_wait"] = True

    state["subscription"] = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(on_update)
    builtins._openarm_static_hold = state
    print("OPENARM_STATIC_HOLD_ARMED")


main()
