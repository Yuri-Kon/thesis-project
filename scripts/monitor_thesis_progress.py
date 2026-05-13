#!/usr/bin/env python3
"""Monitor thesis-final-v1 experiment matrix progress."""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "thesis-final-v1-001"
OUTPUT_DIR = REPO_ROOT / "output" / "experiment" / "thesis-final-matrix" / RUN_ID
LOG_DIR = REPO_ROOT / "data" / "logs"
GROUPS = ["static_top1", "fixed_threshold_gate", "dynamic_no_belief_state", "lite_belief_state"]

run_configs = sorted(OUTPUT_DIR.glob("run_configs/*.json"))
total = len(run_configs)
if total == 0:
    print(f"[monitor] {RUN_ID} — experiment still initializing, no run configs yet.")
    sys.exit(0)

by_group = {g: {"done": 0, "failed": 0, "waiting": 0, "running": 0, "unknown": 0} for g in GROUPS}
total_done = total_failed = total_waiting = total_running = 0
last_ts = ""

for cfg in run_configs:
    name = cfg.stem  # e.g. thesis-final-v1-001_static_top1_t1_trpcage_denovo_short_peptide_r01
    # Find group from name
    group = "?"
    for g in GROUPS:
        if f"_{g}_" in name:
            group = g
            break
    if group == "?":
        continue

    log_path = LOG_DIR / f"{name}.jsonl"
    if not log_path.exists():
        by_group[group]["unknown"] += 1
        continue

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    state = "unknown"
    for line in reversed(lines):  # read last event first
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "TASK_STATUS_CHANGED":
            to_status = event.get("to_status", "")
            if to_status:
                state = to_status
                ts = event.get("timestamp", "") or event.get("ts", "")
                if ts and to_status == "DONE":
                    last_ts = max(last_ts, ts[:19])
            break

    if state == "DONE":
        by_group[group]["done"] += 1
        total_done += 1
    elif state == "FAILED":
        by_group[group]["failed"] += 1
        total_failed += 1
    elif state.startswith("WAITING_"):
        by_group[group]["waiting"] += 1
        total_waiting += 1
    elif state in ("RUNNING", "PLANNING", "SUMMARIZING", "PLANNED", "PATCHING", "REPLANNING", "CREATED"):
        by_group[group]["running"] += 1
        total_running += 1
    else:
        by_group[group][state if state != "unknown" else "unknown"] += 1

total_completed = total_done + total_failed
pct = total_completed / total * 100 if total else 0

print(f"[monitor] {RUN_ID} — {total_completed}/{total} completed ({pct:.0f}%)")

# Summary bar
bar_len = 30
done_bar = int(total_done / max(total, 1) * bar_len)
fail_bar = int(total_failed / max(total, 1) * bar_len)
wait_bar = int(total_waiting / max(total, 1) * bar_len)
print(f"  [{'█' * done_bar}{'█' * fail_bar}{'░' * wait_bar}{' ' * (bar_len-done_bar-fail_bar-wait_bar)}]")
print(f"  {'✓':>3} {total_done:<4d} {'✗':>3} {total_failed:<4d} {'◷':>3} {total_waiting:<4d} {'▶':>3} {total_running:<4d}")
print()

# Per group
print(f"  {'Group':<30} {'Done':>5} {'Fail':>5} {'Wait':>5} {'Actv':>5} {'Total':>5}")
print(f"  {'-'*60}")
current_group = None
for g in GROUPS:
    s = by_group[g]
    gt = s["done"] + s["failed"] + s["waiting"] + s["running"] + s["unknown"]
    done_failed = s["done"] + s["failed"]
    if gt > 0 and done_failed < gt and current_group is None:
        current_group = f"{g} ({done_failed}/{gt} done, {'waiting' if s['waiting'] else 'active'})"
    elif gt > 0 and done_failed == gt:
        current_group = f"{g} ({gt}/{gt} ✓)"
    print(f"  {g:<30} {s['done']:>5d} {s['failed']:>5d} {s['waiting']:>5d} {s['running']:>5d} {gt:>5d}")

if current_group:
    print(f"\n  当前: {current_group}")

if total_waiting > 0:
    print(f"\n  ⚠  {total_waiting} runs waiting for human decision")

if last_ts:
    print(f"  最后完成: {last_ts}")
