"""Create a read-only ROS 2 JointState bridge for the imported OpenArm USD.

Run inside the Isaac Sim Script Editor after ``isaacsim.ros2.bridge`` is
enabled.  The graph publishes state and accepts a namespaced command topic,
but this script itself never publishes a command.
"""
from __future__ import annotations

import omni.graph.core as og
import omni.usd
import usdrt

ARTICULATION_ROOT = "/openarm_v20/Geometry/world/openarm_body_link0"
GRAPH_PATH = "/OpenArmRosBridge"
COMMAND_TOPIC = "/sim/openarm/joint_command"
STATE_TOPIC = "/sim/openarm/joint_states"


def main() -> None:
    stage = omni.usd.get_context().get_stage()
    if stage is None:
        raise RuntimeError("No USD stage is open.")
    if not stage.GetPrimAtPath(ARTICULATION_ROOT).IsValid():
        raise RuntimeError("Articulation root not found: " + ARTICULATION_ROOT)
    if stage.GetPrimAtPath(GRAPH_PATH).IsValid():
        # This script owns this graph path.  Replacing it switches a stalled
        # OnPlaybackTick graph to OnTick without touching the robot USD.
        stage.RemovePrim(GRAPH_PATH)
        print("OPENARM_ROS_GRAPH_REPLACED " + GRAPH_PATH)

    keys = og.Controller.Keys
    og.Controller.edit(
        {"graph_path": GRAPH_PATH, "evaluator_name": "execution"},
        {
            keys.CREATE_NODES: [
                ("OnTick", "omni.graph.action.OnTick"),
                ("ReadSimulationTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                ("PublishJointState", "isaacsim.ros2.bridge.ROS2PublishJointState"),
                ("SubscribeJointState", "isaacsim.ros2.bridge.ROS2SubscribeJointState"),
                ("ArticulationController", "isaacsim.core.nodes.IsaacArticulationController"),
            ],
            keys.CONNECT: [
                ("OnTick.outputs:tick", "PublishJointState.inputs:execIn"),
                ("OnTick.outputs:tick", "SubscribeJointState.inputs:execIn"),
                ("OnTick.outputs:tick", "ArticulationController.inputs:execIn"),
                ("ReadSimulationTime.outputs:simulationTime", "PublishJointState.inputs:timeStamp"),
                ("SubscribeJointState.outputs:jointNames", "ArticulationController.inputs:jointNames"),
                ("SubscribeJointState.outputs:positionCommand", "ArticulationController.inputs:positionCommand"),
                ("SubscribeJointState.outputs:velocityCommand", "ArticulationController.inputs:velocityCommand"),
                ("SubscribeJointState.outputs:effortCommand", "ArticulationController.inputs:effortCommand"),
            ],
            keys.SET_VALUES: [
                ("PublishJointState.inputs:topicName", STATE_TOPIC),
                ("SubscribeJointState.inputs:topicName", COMMAND_TOPIC),
                ("PublishJointState.inputs:targetPrim", [usdrt.Sdf.Path(ARTICULATION_ROOT)]),
                ("ArticulationController.inputs:targetPrim", [usdrt.Sdf.Path(ARTICULATION_ROOT)]),
            ],
        },
    )
    print("OPENARM_ROS_GRAPH_CREATED " + GRAPH_PATH)
    print("STATE_TOPIC=" + STATE_TOPIC)
    print("COMMAND_TOPIC=" + COMMAND_TOPIC)
    print("This script did not publish a command.")


main()
