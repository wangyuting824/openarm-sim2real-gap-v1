# OpenArm Sim2Real Gap v3

v3 delivers a reproducible **14-axis Isaac compare/replay calibration** for the
OpenArm + Isaac Sim stack. It contains the guarded ROS command route, the
Isaac replay bridge, evidence-backed multi-point gap fitting, a complete
importable calibration package, and a reusable Codex skill.

## What is validated

- All 14 arm joints have a named position-response replay term.
- The independent right-J7 v5 trial completed 18/18 waypoints with 49/49
  accepted real+simulation receipts; its within-session held-out replay MAE
  improved from `0.011820` to `0.000918 rad`.
- The v3 calibration schema and 14 enabled entries pass offline validation.
- The artifact modifies **Isaac compare/replay only**. It does not change real
  commands, USD, URDF, Isaac drive parameters, or hardware calibration.

## Import package

Use [`calibration_package/openarm_isaac_replay_calibration_v3/`](calibration_package/openarm_isaac_replay_calibration_v3/):

- `openarm_isaac_replay_calibration_v3.json`: importable 14-axis artifact.
- `IMPORT_README_zh.md`: Chinese deployment and Isaac-only validation guide.
- `SHA256SUMS`: file integrity list.
- `source_evidence/`: compact fit and validation provenance.

The packaged archive is
`calibration_package/openarm_isaac_replay_calibration_v3.tar.gz`.

## Scope

This release calibrates settled joint position response. It does not complete
geometry, camera, contact, payload, dynamic-delay, reliability, or safety
modeling. See [full-stack gap coverage](docs/sim2real_gap_coverage_zh.md) and
[skill logic review](docs/skill_logic_review_zh.md) before expanding to task
optimization.

## Safety

The default router is simulator-only. Any command that can reach hardware
requires a fresh named authorization, bounded manifest, real-state freshness,
single command source, physical workspace confirmation, explicit return, and
post-run router cleanup.
