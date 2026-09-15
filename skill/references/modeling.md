# Modeling reference

## Domain randomization

Randomize parameters that plausibly differ between the modeled task and the real setup. Record each distribution and seed.

Prioritize:

- object mass, center of mass, contact friction, restitution, and initial pose;
- camera extrinsics, focal perturbation, exposure, lighting, material appearance, background, blur/noise;
- control latency, observation latency, actuator rate limits, joint damping, and bounded backlash proxies.

Do not use broad randomization as a substitute for calibration. Keep mechanically identified limits and joint topology fixed unless measurements justify changing them.

## Residual adaptation

Start with a transparent baseline:

`q_real ≈ a ⊙ q_sim + b + h(direction)`, with separate delay `τ`.

Fit static offset `b`, scale `a`, and directional/backlash term `h` from named-joint trajectories. Assess residuals on held-out trajectories. Only then train a bounded model `Δu = f(o, u_sim, e)` where `o` is observation and `e` is the estimated state/model error.

Train the residual on the correction target induced by aligned real/sim observations, not on arbitrary task labels. Cap its output per joint and report both pre- and post-correction error.

## Pi0.5 VLA role

A Pi0.5 VLA may propose an action or select a skill from image/language observation. It should not directly bypass the adapter and supervisor.

Recommended flow:

```text
image + instruction -> VLA skill/action proposal
                  -> frame/action adapter
                  -> residual proposal
                  -> safety supervisor
                  -> real and Isaac executors
                  -> timestamped feedback/data store
```

If force sensing is unavailable, do not claim force-based safety. Use measured joint state, controller status, visual task checks, and configured positional/velocity bounds instead.

## Evaluation

Evaluate both skill and agent on held-out object poses, objects, lighting, and real trials. Report:

- task success and failure category;
- final end-effector/object error where measurable;
- joint tracking RMSE/max error and delay;
- safety stops and the trigger condition;
- residual magnitude and improvement over the no-residual baseline;
- simulation seed/configuration and real-data session identifiers.

A simulation-only gain is not a Sim2Real result. A real result without comparable simulation evidence is not a gap estimate.
