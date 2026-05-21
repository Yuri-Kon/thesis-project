from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Literal, TypeVar, cast

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]

RiskT = TypeVar("RiskT")
RiskFactory = Callable[
    [Literal["warn", "block"], str, str, JsonObject],
    RiskT,
]


def build_safety_risk_flags(
    *,
    fields: JsonObject,
    raw_input: JsonObject,
    forbidden_keywords: Sequence[str],
    make_risk: RiskFactory[RiskT],
) -> list[RiskT]:
    """根据 intake 字段与原始输入生成安全预检风险标记。"""

    risk_flags: list[RiskT] = []
    safety_text = safety_search_text(fields, raw_input)
    _append_blocked_use_risk(risk_flags, safety_text=safety_text, make_risk=make_risk)
    _append_forbidden_motif_risks(risk_flags, fields=fields, make_risk=make_risk)
    _append_forbidden_function_risks(
        risk_flags,
        fields=fields,
        raw_input=raw_input,
        make_risk=make_risk,
    )
    _append_high_risk_intent(
        risk_flags,
        fields=fields,
        raw_input=raw_input,
        forbidden_keywords=forbidden_keywords,
        make_risk=make_risk,
    )
    _append_safety_level_warning(
        risk_flags,
        fields=fields,
        safety_text=safety_text,
        make_risk=make_risk,
    )
    return risk_flags


def resolve_precheck_action(
    risk_levels: Sequence[str],
) -> Literal["ok", "warn", "block"]:
    """将风险等级集合折叠为 TaskIntakeSafetyCheck.action。"""

    if any(level == "block" for level in risk_levels):
        return "block"
    if any(level == "warn" for level in risk_levels):
        return "warn"
    return "ok"


def coerce_string_list(value: JsonValue) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def text_mentions_forbidden_function(
    fields: JsonObject,
    raw_input: JsonObject,
    forbidden_function: str,
) -> bool:
    target = forbidden_function.strip().lower()
    if not target:
        return False
    return target in safety_search_text(fields, raw_input)


def mentions_high_risk_intent(
    fields: JsonObject,
    raw_input: JsonObject,
    *,
    forbidden_keywords: Sequence[str],
) -> bool:
    haystack = safety_search_text(fields, raw_input)
    return any(keyword in haystack for keyword in forbidden_keywords)


def safety_search_text(fields: JsonObject, raw_input: JsonObject) -> str:
    pieces: list[str] = []
    raw_text = raw_input.get("text")
    if isinstance(raw_text, str):
        pieces.append(raw_text)
    for name in (
        "goal_summary",
        "objective_description",
        "motif_pattern",
        "binding_partner",
        "target_ligand",
    ):
        value = fields.get(name)
        if isinstance(value, str):
            pieces.append(value)
    return "\n".join(pieces).lower()


def _append_blocked_use_risk(
    risk_flags: list[RiskT],
    *,
    safety_text: str,
    make_risk: RiskFactory[RiskT],
) -> None:
    blocked_terms = ("weapon", "bioweapon", "病原增强")
    if any(term in safety_text for term in blocked_terms):
        risk_flags.append(
            make_risk(
                "block",
                "SAFETY_INPUT_BLOCK",
                "input appears to request a blocked unsafe biological use",
                {"terms": cast(JsonValue, list(blocked_terms))},
            )
        )


def _append_forbidden_motif_risks(
    risk_flags: list[RiskT],
    *,
    fields: JsonObject,
    make_risk: RiskFactory[RiskT],
) -> None:
    sequence = fields.get("sequence")
    forbidden_motifs = fields.get("forbidden_motifs")
    if not isinstance(sequence, str) or not isinstance(forbidden_motifs, list):
        return
    normalized_sequence = sequence.upper()
    for motif in forbidden_motifs:
        if isinstance(motif, str) and motif.upper() in normalized_sequence:
            risk_flags.append(
                make_risk(
                    "warn",
                    "FORBIDDEN_MOTIF_PRESENT",
                    f"forbidden_motifs contains motif present in sequence: {motif}",
                    {"motif": motif},
                )
            )


def _append_forbidden_function_risks(
    risk_flags: list[RiskT],
    *,
    fields: JsonObject,
    raw_input: JsonObject,
    make_risk: RiskFactory[RiskT],
) -> None:
    for forbidden_function in coerce_string_list(fields.get("forbidden_functions")):
        if text_mentions_forbidden_function(fields, raw_input, forbidden_function):
            message = (
                "input requests a function listed in forbidden_functions: "
                f"{forbidden_function}"
            )
            risk_flags.append(
                make_risk(
                    "block",
                    "FORBIDDEN_FUNCTION_REQUESTED",
                    message,
                    {"forbidden_function": forbidden_function},
                )
            )


def _append_high_risk_intent(
    risk_flags: list[RiskT],
    *,
    fields: JsonObject,
    raw_input: JsonObject,
    forbidden_keywords: Sequence[str],
    make_risk: RiskFactory[RiskT],
) -> None:
    if mentions_high_risk_intent(
        fields,
        raw_input,
        forbidden_keywords=forbidden_keywords,
    ):
        risk_flags.append(
            make_risk(
                "block",
                "HIGH_RISK_BIOFUNCTION_REQUEST",
                "input appears to request a high-risk biological function",
                {"keywords": cast(JsonValue, list(forbidden_keywords))},
            )
        )


def _append_safety_level_warning(
    risk_flags: list[RiskT],
    *,
    fields: JsonObject,
    safety_text: str,
    make_risk: RiskFactory[RiskT],
) -> None:
    if fields.get("safety_level") == "S2" or any(
        term in safety_text for term in ("pathogenic", "毒性", "病原")
    ):
        risk_flags.append(
            make_risk(
                "warn",
                "SAFETY_INPUT_WARN",
                "input may need additional safety review before task creation",
                {"safety_level": fields.get("safety_level")},
            )
        )
