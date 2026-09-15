# Open-source Sim2Real resources

Use these as diagnosis and design references, not as unreviewed patches. Search
an upstream project's official documentation and issue tracker using the
concrete observed symptom, Isaac/ROS version, and minimal evidence artifact.
Always reproduce an advice in simulator-only mode before a physical trial.

| Resource | Use it for | OpenArm application |
|---|---|---|
| [Isaac Lab](https://isaac-sim.github.io/IsaacLab/v2.3.0/index.html) | Isaac-native robot learning, modular environments, domain randomization | Keep OpenArm action/observation names in the adapter profile; randomize only measured uncertainty ranges. |
| [Isaac Lab policy transfer guidance](https://isaac-sim.github.io/IsaacLab/release/3.0.0/source/concepts/transfer_policies_between_physx_and_newton.html) | friction, mass/inertia, joint gains/friction, actuator response and observation noise | Start from hardware/Isaac measurements; use plausible distributions and a deterministic nominal evaluation. |
| [Isaac Lab gear assembly deployment guidance](https://isaac-sim.github.io/IsaacLab/main/source/policy_deployment/02_gear_assembly/gear_assembly_policy.html) | incremental joint actions and action-scale selection | Keep the real router's bounded per-step command and measure tracking before policy deployment. |
| [robosuite](https://github.com/ARISE-Initiative/robosuite) and its [domain-randomization demos](https://github.com/ARISE-Initiative/robosuite/blob/master/docs/demos.md) | MuJoCo baselines, visual randomization, sensor corruption/delay/frequency models | Use as a cross-simulator baseline for the existing MuJoCo assets, not as a replacement for Isaac control diagnosis. |
| [LeRobot](https://github.com/huggingface/lerobot) | dataset capture, policy training/deployment and Pi-family integration | Feed only audited real/sim trajectories and preserve calibration/config provenance. |
| [ros2_control](https://control.ros.org/) | hardware interface lifecycle, controller contracts and debugging | Diagnose controller/feedback behavior on the real host; do not infer CAN health from Isaac state. |

## Search protocol

1. Produce the local evidence first: health JSON, drive probe, ROS graph,
   tracking JSON and exact software versions.
2. Search upstream official docs/issues with the error string and component,
   for example `UsdPhysics DriveAPI target position Isaac Sim 6` or
   `ros2_control stale joint state forward position controller`.
3. Record the link, version compatibility, proposed change, expected effect
   and rollback in the integration ledger.
4. Apply only a reversible simulator-only candidate first. A repository issue
   may explain a symptom but is not proof that it matches this robot.

The agent can perform this research automatically when network access is
available. It must not automatically install a third-party package, alter the
real controller, or execute a physical trial based solely on an issue comment.
