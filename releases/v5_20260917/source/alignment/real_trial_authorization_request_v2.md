# Real-trial authorization request

**Trial ID:** `openarm_real_sim_bimanual_offset_identification_v2`

**Purpose:** measure per-joint real/Isaac position, direction, repeatability,
and timing gaps. This is not a calibration-application trial.

## Requested physical action

Authorize the agent to use the existing real bringup or, if it is not active,
to start `start_real_openarm.sh` and enable the motors for this named trial.
The agent will then command one arm joint at a time through the guarded router.

- 14 arm joints, serially; fingers excluded.
- Each non-J4 joint: measured start → `+0.05` → start → `−0.05` → start →
  `+0.10` → start; three repetitions.
- J4: positive-only safe sequence because its configured lower limit is zero.
- Holds: 3 s; router continuous publication: 50 Hz.
- Expected duration: about 15 minutes, including preflight and serial returns.
- Total excursion: at most 0.15 rad; substep: at most 0.025 rad.
- Each joint returns to its measured start before the next joint.
- The router stops on stale state, limit violation, Isaac target/return error
  above 0.01 rad, duplicate command publisher, or operator stop.

## Required operator confirmation

Reply with the exact trial ID and confirm all items below are true:

1. Emergency stop is released and can be triggered immediately.
2. Work area is clear; no person is inside the arm workspace.
3. Both arms are in a known safe posture.
4. A person is at the power-disconnect location throughout the trial.
5. No other process is publishing real arm commands.
6. The operator authorizes motor enable/use and all physical motion in this
   named trial only.

Approval is single-use for this manifest. It does not authorize retries,
changed limits, calibration application, USD/URDF edits, or other commands.
