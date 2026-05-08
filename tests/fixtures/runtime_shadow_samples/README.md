Runtime shadow replay samples

Purpose:
- Provide minimal offline replay inputs for runtime-state, snapshot, audit-log,
  and shadow-output focused tests.
- Keep the samples small enough for local and CI reuse.

Source:
- Derived from the frozen experiment lineage around a baseline smoke run.
- Reduced to the smallest event/snapshot/report subset needed for deterministic
  replay in `tests/unit/test_w12_vertical_experiment.py`.

Usage:
- Load the JSON sample with `load_replay_sample()`.
- Materialize it into a temp directory with `materialize_replay_sample()`.
- Replay and extract metrics with `replay_sample()` or `replay_samples()`.
