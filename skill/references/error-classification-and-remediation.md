# Error classification and Isaac remediation

Read this reference after a repeated, paired, settled joint trajectory has been
recorded. It defines how to turn measured differences into *candidates* for
simulation repair. It does not authorize real commands or permanent model edits.

## Required evidence

For each named joint, collect paired real/Isaac state at three or more target
magnitudes, with positive and negative approaches, repeated at least three
times. Keep samples by timestamp and retain raw values. Exclude any run where
one endpoint did not track its declared target; that is an integration defect,
not Sim2Real evidence.

Run:

```bash
python3 alignment/fit_openarm_gap_model.py \
  --input-glob 'alignment/results/<trial>/openarm_*_joint*.json' \
  --output alignment/results/<trial>/gap_model_candidates.json
```

The output is an offline candidate file. It never commands hardware or changes
USD, URDF, or Isaac drives.

## Classification and repair order

| Evidence | Interpretation | Isaac-side response | Validation |
| --- | --- | --- | --- |
| Stable same-direction residual, low repeat spread | Static zero/frame offset | Add `q_sim_corrected = a*q_sim + b` only in the versioned compare/replay transform. | Hold out a repetition and confirm terminal residual drops without increasing variance. |
| Residual grows with target magnitude; fitted `a` differs from 1 | Scale, target-unit, axis, transmission, or limit mismatch | Audit radians/degrees, sign, axis, drive target units, gear/transmission mapping, and limits. Correct the mapping layer first. | Sim-only tracking at multiple targets, then held-out paired replay. |
| Positive and negative approach residuals differ | Backlash, stiction, friction, deadband, or direction-dependent mapping | Keep stateful `h(direction)` in replay/control wrapper; model bounded friction, damping, deadband, or backlash proxy in Isaac. Do not encode it as a single joint-origin offset. | Alternate approach direction over held-out targets and compare each direction separately. |
| Mean residual is near zero but residual standard deviation is high | Random noise or unmodelled state/load | Estimate distributions and randomize damping, friction, latency, observation noise, payload, and control-rate jitter within measured ranges. Train/evaluate a robust policy over seeds. | Report held-out mean, standard deviation, p95, and task success across seeds. |
| Timestamped response onset/t90/t95 differs | Command, actuator, observation, or scheduling delay | Add explicit command and observation buffers, matching control rate and hold behavior; retain separate `tau_command` and `tau_observation`. | Compare timestamped ramps, delay distribution, settling time, and overshoot. |

## Escalation rules

1. Repair a failed Isaac sim-only drive or bridge before estimating any gap for
   that joint.
2. Prefer compare/replay transforms first. Permanent USD/URDF or Isaac drive
   changes require a sim-only regression and a held-out paired replay.
3. A deterministic correction is invalid when the held-out residual variance
   remains large or direction changes its sign.
4. Never compensate by changing real motor gains, limits, or commands unless a
   separately authorized hardware trial explicitly calls for it.
