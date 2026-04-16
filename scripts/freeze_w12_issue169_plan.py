#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path("configs/experiments/w12_issue169_plan_freeze.json")
DEFAULT_OUTPUT_ROOT = Path("output/experiment/w12-expr-0")


@dataclass(frozen=True)
class IssueWindow:
    number: int
    title: str
    track: str
    start: date
    end: date
    hard_blocked_by: tuple[int, ...]
    soft_sync: tuple[int, ...]

    @property
    def duration_days(self) -> int:
        return (self.end - self.start).days + 1


def _json_dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"config must be a JSON object: {path}")
    return payload


def _parse_date(value: Any, *, field: str, issue_number: int) -> date:
    if not isinstance(value, str):
        raise ValueError(f"issue #{issue_number} field '{field}' must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"issue #{issue_number} field '{field}' invalid date: {value}"
        ) from exc


def _parse_int_list(value: Any, *, field: str, issue_number: int) -> tuple[int, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"issue #{issue_number} field '{field}' must be a list[int]")
    items: list[int] = []
    for raw in value:
        if not isinstance(raw, int):
            raise ValueError(
                f"issue #{issue_number} field '{field}' must contain only int values"
            )
        items.append(raw)
    return tuple(items)


def _load_issue_windows(config: dict[str, Any]) -> dict[int, IssueWindow]:
    raw_issues = config.get("issues")
    if not isinstance(raw_issues, list) or not raw_issues:
        raise ValueError("config.issues must be a non-empty list")

    issues: dict[int, IssueWindow] = {}
    for raw in raw_issues:
        if not isinstance(raw, dict):
            raise ValueError("config.issues entries must be objects")
        number = raw.get("number")
        if not isinstance(number, int):
            raise ValueError("each issue entry must include integer field 'number'")
        if number in issues:
            raise ValueError(f"duplicated issue number in config: {number}")

        title = str(raw.get("title") or f"issue-{number}")
        track = str(raw.get("track") or "Unknown")
        start = _parse_date(raw.get("start"), field="start", issue_number=number)
        end = _parse_date(raw.get("end"), field="end", issue_number=number)
        if end < start:
            raise ValueError(f"issue #{number} has end date earlier than start date")

        issues[number] = IssueWindow(
            number=number,
            title=title,
            track=track,
            start=start,
            end=end,
            hard_blocked_by=_parse_int_list(
                raw.get("hard_blocked_by"), field="hard_blocked_by", issue_number=number
            ),
            soft_sync=_parse_int_list(raw.get("soft_sync"), field="soft_sync", issue_number=number),
        )
    return issues


def _build_internal_graph(
    issues: dict[int, IssueWindow]
) -> tuple[dict[int, set[int]], dict[int, int], dict[int, list[int]]]:
    graph: dict[int, set[int]] = {number: set() for number in issues}
    indegree: dict[int, int] = {number: 0 for number in issues}
    external_blockers: dict[int, list[int]] = defaultdict(list)

    for issue in issues.values():
        for blocker in issue.hard_blocked_by:
            if blocker in issues:
                if issue.number not in graph[blocker]:
                    graph[blocker].add(issue.number)
                    indegree[issue.number] += 1
            else:
                external_blockers[issue.number].append(blocker)

    for issue_number in external_blockers:
        external_blockers[issue_number].sort()
    return graph, indegree, dict(external_blockers)


def _track_rank_map(config: dict[str, Any]) -> dict[str, int]:
    rank: dict[str, int] = {"Planning": 0}
    policy = config.get("execution_order_policy")
    if isinstance(policy, list):
        for index, item in enumerate(policy, start=1):
            if isinstance(item, str) and item:
                rank[item] = index
    return rank


def _topological_order(
    *,
    issues: dict[int, IssueWindow],
    graph: dict[int, set[int]],
    indegree: dict[int, int],
    track_rank: dict[str, int],
) -> list[int]:
    queue: deque[int] = deque(
        sorted(
            [number for number, value in indegree.items() if value == 0],
            key=lambda number: (
                issues[number].start,
                track_rank.get(issues[number].track, 999),
                number,
            ),
        )
    )
    mutable_indegree = dict(indegree)
    order: list[int] = []

    while queue:
        current = queue.popleft()
        order.append(current)
        for nxt in sorted(graph[current]):
            mutable_indegree[nxt] -= 1
            if mutable_indegree[nxt] == 0:
                queue.append(nxt)
        queue = deque(
            sorted(
                queue,
                key=lambda number: (
                    issues[number].start,
                    track_rank.get(issues[number].track, 999),
                    number,
                ),
            )
        )

    if len(order) != len(issues):
        dangling = sorted(number for number in issues if number not in order)
        raise ValueError(f"dependency cycle detected among issues: {dangling}")
    return order


def _has_path(graph: dict[int, set[int]], start: int, target: int) -> bool:
    if start == target:
        return True
    visited: set[int] = set()
    queue: deque[int] = deque([start])
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        for nxt in graph.get(current, set()):
            if nxt == target:
                return True
            if nxt not in visited:
                queue.append(nxt)
    return False


def _critical_path(
    *,
    issues: dict[int, IssueWindow],
    graph: dict[int, set[int]],
    topo_order: list[int],
) -> tuple[list[int], int]:
    dist: dict[int, int] = {number: issues[number].duration_days for number in issues}
    prev: dict[int, int] = {}

    for current in topo_order:
        base = dist[current]
        for nxt in graph.get(current, set()):
            candidate = base + issues[nxt].duration_days
            if candidate > dist[nxt]:
                dist[nxt] = candidate
                prev[nxt] = current

    end_node = max(dist, key=dist.get)
    total_days = dist[end_node]
    chain: list[int] = [end_node]
    while chain[-1] in prev:
        chain.append(prev[chain[-1]])
    chain.reverse()
    return chain, total_days


def _date_overlap(a: IssueWindow, b: IssueWindow) -> bool:
    return max(a.start, b.start) <= min(a.end, b.end)


def _parallel_pairs(
    *,
    issues: dict[int, IssueWindow],
    graph: dict[int, set[int]],
) -> list[dict[str, Any]]:
    numbers = sorted(issues.keys())
    rows: list[dict[str, Any]] = []
    for idx, left in enumerate(numbers):
        for right in numbers[idx + 1 :]:
            if _has_path(graph, left, right) or _has_path(graph, right, left):
                continue
            issue_left = issues[left]
            issue_right = issues[right]
            if not _date_overlap(issue_left, issue_right):
                continue
            rows.append(
                {
                    "issues": [left, right],
                    "tracks": [issue_left.track, issue_right.track],
                    "window_overlap": [
                        max(issue_left.start, issue_right.start).isoformat(),
                        min(issue_left.end, issue_right.end).isoformat(),
                    ],
                    "reason": "no hard dependency path and overlapping execution window",
                }
            )
    return rows


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _render_markdown(
    *,
    result: dict[str, Any],
    issues: dict[int, IssueWindow],
) -> str:
    lines: list[str] = []
    lines.append("# W12 Issue #169 Execution Plan Freeze Index")
    lines.append("")
    lines.append(f"- plan_freeze_id: `{result['plan_freeze_id']}`")
    lines.append(f"- generated_at: `{result['generated_at']}`")
    lines.append(f"- source_config: `{result['source_config_path']}`")
    lines.append("")
    lines.append("## Schedule")
    lines.append("")
    lines.append("| issue | track | start | end | duration_days | hard_blocked_by |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for item in result["schedule"]:
        blocked = ",".join(str(value) for value in item["hard_blocked_by"]) or "-"
        lines.append(
            f"| #{item['number']} | {item['track']} | {item['start']} | "
            f"{item['end']} | {item['duration_days']} | {blocked} |"
        )
    lines.append("")
    lines.append("## Critical Path")
    lines.append("")
    critical_issues = " -> ".join(f"#{number}" for number in result["critical_path"]["issues"])
    lines.append(f"- chain: {critical_issues}")
    lines.append(f"- total_duration_days: {result['critical_path']['duration_days']}")
    lines.append("")
    lines.append("## Non-Parallel Items")
    lines.append("")
    for item in result["non_parallel_items"]:
        lines.append(f"- #{item['from']} -> #{item['to']} ({item['reason']})")
    lines.append("")
    lines.append("## Parallel Candidates")
    lines.append("")
    if result["parallel_items"]:
        for row in result["parallel_items"]:
            pair = row["issues"]
            overlap = row["window_overlap"]
            lines.append(
                f"- #{pair[0]} + #{pair[1]} (overlap={overlap[0]}..{overlap[1]})"
            )
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Acceptance Checks")
    lines.append("")
    checks = result["validations"]
    lines.append(f"- has_time_windows: `{checks['has_time_windows']}`")
    lines.append(f"- dependency_cycle_free: `{checks['dependency_cycle_free']}`")
    lines.append(
        f"- data_issue_on_critical_front: `{checks['data_issue_on_critical_front']}`"
    )
    lines.append(
        "- data_first_reason: "
        + checks["data_first_reason"]
    )
    if checks["external_hard_blockers"]:
        lines.append("- external_hard_blockers:")
        for issue_number, blockers in sorted(checks["external_hard_blockers"].items()):
            lines.append(f"  - issue #{issue_number}: {blockers}")
    lines.append("")
    return "\n".join(lines) + "\n"


def freeze_issue169_plan(
    *,
    config_path: Path,
    output_root: Path,
    plan_id: str | None,
) -> dict[str, Any]:
    config = _read_json(config_path)
    issues = _load_issue_windows(config)

    graph, indegree, external_blockers = _build_internal_graph(issues)
    track_rank = _track_rank_map(config)
    topo_order = _topological_order(
        issues=issues, graph=graph, indegree=indegree, track_rank=track_rank
    )
    critical_chain, critical_days = _critical_path(
        issues=issues, graph=graph, topo_order=topo_order
    )
    parallel_items = _parallel_pairs(issues=issues, graph=graph)

    # Acceptance checks for issue #169
    has_time_windows = all(issue.start <= issue.end for issue in issues.values())
    dependency_cycle_free = True
    data_targets = [171, 172, 173, 174]
    data_issue = issues.get(170)
    if data_issue is None:
        raise ValueError("issue #170 must exist in plan config for acceptance validation")
    data_first_ok = (
        all(data_issue.start <= issues[target].start for target in data_targets if target in issues)
        and all(_has_path(graph, 170, target) for target in (171, 172, 173, 174) if target in issues)
    )
    data_first_reason = (
        "issue #170 starts earliest among downstream experiments and reaches #171/#172/#173/#174"
        if data_first_ok
        else "issue #170 does not satisfy earliest-start and dependency reachability constraints"
    )

    resolved_plan_id = plan_id or str(config.get("plan_id") or "w12-plan-freeze")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    freeze_id = f"{resolved_plan_id}-{timestamp}"
    output_dir = output_root / freeze_id
    output_dir.mkdir(parents=True, exist_ok=False)

    schedule = [
        {
            "number": issue.number,
            "title": issue.title,
            "track": issue.track,
            "start": issue.start.isoformat(),
            "end": issue.end.isoformat(),
            "duration_days": issue.duration_days,
            "hard_blocked_by": list(issue.hard_blocked_by),
            "soft_sync": list(issue.soft_sync),
        }
        for issue in sorted(issues.values(), key=lambda item: item.number)
    ]

    non_parallel_items: list[dict[str, Any]] = []
    for src, targets in sorted(graph.items()):
        for dst in sorted(targets):
            non_parallel_items.append(
                {
                    "from": src,
                    "to": dst,
                    "reason": "hard_dependency",
                }
            )

    result = {
        "issue_id": int(config.get("issue_id") or 169),
        "plan_freeze_id": freeze_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_config_path": str(config_path),
        "source_config_hash": _hash_payload(config),
        "execution_order_policy": config.get("execution_order_policy", []),
        "topological_order": topo_order,
        "schedule": schedule,
        "critical_path": {
            "issues": critical_chain,
            "duration_days": critical_days,
        },
        "non_parallel_items": non_parallel_items,
        "parallel_items": parallel_items,
        "validations": {
            "has_time_windows": has_time_windows,
            "dependency_cycle_free": dependency_cycle_free,
            "data_issue_on_critical_front": data_first_ok,
            "data_first_reason": data_first_reason,
            "external_hard_blockers": external_blockers,
        },
        "artifacts": {
            "output_dir": str(output_dir),
            "execution_plan_index_json": str(output_dir / "execution_plan_index.json"),
            "execution_plan_index_md": str(output_dir / "execution_plan_index.md"),
        },
    }

    with (output_dir / "execution_plan_index.json").open("w", encoding="utf-8") as handle:
        handle.write(_json_dump(result) + "\n")

    markdown = _render_markdown(result=result, issues=issues)
    with (output_dir / "execution_plan_index.md").open("w", encoding="utf-8") as handle:
        handle.write(markdown)

    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Freeze issue #169 experiment plan with dependency/timeline validation.",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--plan-id", type=str, default=None)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    result = freeze_issue169_plan(
        config_path=args.config,
        output_root=args.output_root,
        plan_id=args.plan_id,
    )
    print("Issue #169 plan freeze completed")
    print(
        _json_dump(
            {
                "plan_freeze_id": result["plan_freeze_id"],
                "topological_order": result["topological_order"],
                "data_issue_on_critical_front": result["validations"][
                    "data_issue_on_critical_front"
                ],
            }
        )
    )
    if not result["validations"]["data_issue_on_critical_front"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
