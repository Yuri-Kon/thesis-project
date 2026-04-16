from __future__ import annotations

import re
from typing import Any

from src.models.contracts import ProteinDesignTask

_DE_NOVO_GOAL_TYPE = "de_novo_design"

_RANGE_PATTERNS = (
    re.compile(
        r"(?P<low>\d{2,4})\s*(?:-|to|~|～|—|–|至)\s*(?P<high>\d{2,4})\s*(?:aa|amino acids?|residues?|个氨基酸|氨基酸)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"长度(?:为|在)?\s*(?P<low>\d{2,4})\s*(?:-|到|至|~|～|—|–)\s*(?P<high>\d{2,4})",
        re.IGNORECASE,
    ),
)
_EXACT_PATTERNS = (
    re.compile(
        r"(?:length|长度)(?:\s*(?:is|为|约|around|about))?\s*(?P<value>\d{2,4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<value>\d{2,4})\s*(?:aa|amino acids?|residues?|个氨基酸|氨基酸)",
        re.IGNORECASE,
    ),
)
_PDB_PATH_PATTERN = re.compile(r"(?P<path>[\w./-]+\.pdb)\b", re.IGNORECASE)
_PDB_ID_PATTERN = re.compile(r"\b(?P<pdb_id>[0-9][a-zA-Z0-9]{3})\b")
_SEQUENCE_PATTERN = re.compile(r"\b(?P<sequence>[ACDEFGHIKLMNPQRSTVWY]{8,})\b")

_REMOTE_HINTS = ("remote", "nim", "api", "在线", "远程")
_LOCAL_HINTS = ("local", "offline", "本地", "离线")
_STRUCTURE_HINTS = ("structure", "fold", "折叠", "结构")
_SEQUENCE_HINTS = (
    "sequence",
    "protein",
    "proteins",
    "蛋白",
    "蛋白质",
    "序列",
    "design",
    "设计",
    "scaffold",
    "solubility",
    "soluble",
    "enzyme",
    "binding",
    "binder",
    "pocket",
)


def enrich_task_from_goal(task: ProteinDesignTask) -> ProteinDesignTask:
    """Infer minimal structured constraints from a free-form goal string.

    This parser is intentionally conservative:
    - keep all existing constraints untouched unless a field is missing
    - only infer fields that the current planner/executor can already consume
    - annotate metadata with the applied inference for auditability
    """

    goal = task.goal.strip()
    if not goal:
        return task

    constraints = dict(task.constraints or {})
    if not _should_parse_goal(goal, constraints):
        return task
    metadata = dict(task.metadata or {})
    parse_notes: dict[str, Any] = dict(metadata.get("nl_parse") or {})
    changed = False

    if not isinstance(constraints.get("sequence"), str) or not str(constraints.get("sequence")).strip():
        inferred_sequence = _infer_sequence(goal)
        if inferred_sequence is not None:
            constraints["sequence"] = inferred_sequence
            parse_notes["sequence"] = inferred_sequence
            changed = True

    inferred_goal_type = _infer_goal_type(goal, constraints)
    if inferred_goal_type and not constraints.get("goal_type"):
        constraints["goal_type"] = inferred_goal_type
        parse_notes["goal_type"] = inferred_goal_type
        changed = True

    if not isinstance(constraints.get("prompt"), str) or not str(constraints.get("prompt")).strip():
        constraints["prompt"] = goal
        parse_notes["prompt_source"] = "goal"
        changed = True

    length_range = constraints.get("length_range")
    if not _is_valid_length_range(length_range):
        inferred_range = _infer_length_range(goal)
        if inferred_range is not None:
            constraints["length_range"] = inferred_range
            parse_notes["length_range"] = inferred_range
            changed = True

    if not isinstance(constraints.get("prefer_remote"), bool):
        prefer_remote = _infer_prefer_remote(goal)
        if prefer_remote is not None:
            constraints["prefer_remote"] = prefer_remote
            parse_notes["prefer_remote"] = prefer_remote
            changed = True

    if not isinstance(constraints.get("template"), str) and not isinstance(
        constraints.get("structure_template_pdb"), str
    ) and not isinstance(constraints.get("pdb_path"), str):
        template = _infer_template(goal)
        if template is not None:
            constraints["template"] = template
            parse_notes["template"] = template
            changed = True

    if not changed:
        return task

    metadata["nl_parse"] = {
        **parse_notes,
        "source": "task_goal_parser_v1",
        "applied": True,
    }
    return task.model_copy(
        update={
            "constraints": constraints,
            "metadata": metadata,
        },
        deep=True,
    )


def _infer_goal_type(goal: str, constraints: dict[str, Any]) -> str | None:
    if constraints.get("goal_type"):
        return None
    if isinstance(constraints.get("sequence"), str) and str(constraints.get("sequence")).strip():
        return None
    lowered = goal.lower()
    if any(token in lowered for token in _SEQUENCE_HINTS):
        return _DE_NOVO_GOAL_TYPE
    if any(token in lowered for token in _STRUCTURE_HINTS):
        return _DE_NOVO_GOAL_TYPE
    return None


def _infer_length_range(goal: str) -> list[int] | None:
    for pattern in _RANGE_PATTERNS:
        match = pattern.search(goal)
        if match is None:
            continue
        low = int(match.group("low"))
        high = int(match.group("high"))
        if 0 < low <= high:
            return [low, high]

    for pattern in _EXACT_PATTERNS:
        match = pattern.search(goal)
        if match is None:
            continue
        value = int(match.group("value"))
        if value > 0:
            return [value, value]
    return None


def _infer_prefer_remote(goal: str) -> bool | None:
    lowered = goal.lower()
    if any(token in lowered for token in _REMOTE_HINTS):
        return True
    if any(token in lowered for token in _LOCAL_HINTS):
        return False
    return None


def _infer_template(goal: str) -> str | None:
    path_match = _PDB_PATH_PATTERN.search(goal)
    if path_match is not None:
        return path_match.group("path")
    if any(token in goal.lower() for token in _STRUCTURE_HINTS):
        pdb_id_match = _PDB_ID_PATTERN.search(goal)
        if pdb_id_match is not None:
            return pdb_id_match.group("pdb_id").upper()
    return None


def _infer_sequence(goal: str) -> str | None:
    match = _SEQUENCE_PATTERN.search(goal.upper())
    if match is None:
        return None
    return match.group("sequence")


def _is_valid_length_range(value: Any) -> bool:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return False
    try:
        low = int(value[0])
        high = int(value[1])
    except (TypeError, ValueError):
        return False
    return low > 0 and high >= low


def _should_parse_goal(goal: str, constraints: dict[str, Any]) -> bool:
    if constraints.get("goal_type"):
        return True
    if any(
        isinstance(constraints.get(key), str) and str(constraints.get(key)).strip()
        for key in ("sequence", "template", "structure_template_pdb", "pdb_path")
    ):
        return False
    lowered = goal.lower()
    return any(token in lowered for token in (_SEQUENCE_HINTS + _STRUCTURE_HINTS))
