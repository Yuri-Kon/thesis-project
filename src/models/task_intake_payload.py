from __future__ import annotations

import re
from collections.abc import Set as AbstractSet
from typing import cast

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | JsonObject | JsonArray
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]


def build_rule_extraction_payload(
    text: str,
    *,
    allowed_tool_ids: AbstractSet[str],
    source_value: str,
) -> JsonObject:
    """根据自然语言规则抽取 task intake draft payload。"""

    builder = _RuleExtractionBuilder(
        text=text,
        allowed_tool_ids=allowed_tool_ids,
        source_value=source_value,
    )
    builder.add_task_kind()
    builder.add_objective_type()
    builder.add_length_range()
    builder.add_design_count()
    builder.add_run_profile()
    builder.add_safety_level()
    builder.add_plan_confirmation()
    builder.add_tool_preferences()
    builder.add_goal_summary()
    return builder.payload()


class _RuleExtractionBuilder:
    def __init__(
        self,
        *,
        text: str,
        allowed_tool_ids: AbstractSet[str],
        source_value: str,
    ) -> None:
        self.text: str = text
        self.lowered: str = text.lower()
        self.allowed_tool_ids: AbstractSet[str] = allowed_tool_ids
        self.source_value: str = source_value
        self.fields: JsonObject = {}
        self.source_spans: list[str] = []

    @property
    def design_intent(self) -> bool:
        return any(
            marker in self.lowered
            for marker in ("design", "de novo", "de-novo", "generate", "protein")
        ) or any(marker in self.text for marker in ("设计", "生成", "蛋白", "从头"))

    def add_field(
        self,
        field_name: str,
        value: JsonValue,
        confidence: float,
        source_span: str | None = None,
    ) -> None:
        self.fields[field_name] = {
            "value": value,
            "source": self.source_value,
            "confidence": confidence,
            "source_span": source_span,
        }
        if source_span:
            self.source_spans.append(source_span)

    def add_task_kind(self) -> None:
        if "de novo" in self.lowered or "de-novo" in self.lowered or "从头" in self.text:
            self.add_field("task_kind", "de_novo_design", 0.86, "de novo")
        elif "评估" in self.text or "evaluate" in self.lowered:
            self.add_field(
                "task_kind",
                "sequence_evaluation",
                0.84,
                _first_present_span(self.text, ["评估", "evaluate"]),
            )
        elif "template" in self.lowered or "模板" in self.text:
            self.add_field(
                "task_kind",
                "template_constrained_design",
                0.84,
                _first_present_span(self.text, ["模板", "template"]),
            )
        elif self.design_intent:
            self.add_field(
                "task_kind",
                "de_novo_design",
                0.80,
                _first_present_span(self.text, ["设计", "design", "生成", "protein"]),
            )

    def add_objective_type(self) -> None:
        if "稳定" in self.text or "stability" in self.lowered or "stable" in self.lowered:
            self.add_field(
                "objective_type",
                "stability",
                0.88,
                _first_present_span(self.text, ["稳定", "stability", "stable"]),
            )
        elif "binding" in self.lowered or "结合" in self.text:
            self.add_field(
                "objective_type",
                "binding",
                0.72,
                _first_present_span(self.text, ["binding", "结合"]),
            )
        elif "结构" in self.text or "structure" in self.lowered:
            self.add_field(
                "objective_type",
                "structure",
                0.78,
                _first_present_span(self.text, ["结构", "structure"]),
            )
        elif "活性" in self.text or "activity" in self.lowered:
            self.add_field(
                "objective_type",
                "activity",
                0.76,
                _first_present_span(self.text, ["活性", "activity"]),
            )

    def add_length_range(self) -> None:
        range_match = re.search(r"(\d{2,4})\s*(?:-|~|到|至)\s*(\d{2,4})", self.text)
        if range_match:
            self.add_field(
                "length_range",
                [int(range_match.group(1)), int(range_match.group(2))],
                0.92,
                range_match.group(0),
            )
            return

        approx_match = re.search(
            r"(?:约|大约|around|about)?\s*(\d{2,4})\s*(?:个)?\s*(?:aa|氨基酸)",
            self.text,
            re.IGNORECASE,
        )
        if approx_match:
            center = int(approx_match.group(1))
            self.add_field(
                "length_range",
                [max(1, center - 20), center + 20],
                0.91,
                approx_match.group(0),
            )

    def add_design_count(self) -> None:
        count_match = re.search(
            r"(\d{1,2})\s*(?:个)?(?:候选|candidate)",
            self.text,
            re.IGNORECASE,
        )
        if count_match:
            self.add_field("design_count", int(count_match.group(1)), 0.84, count_match.group(0))

    def add_run_profile(self) -> None:
        if "快" in self.text or "fast" in self.lowered:
            self.add_field("run_profile", "fast_smoke", 0.82, _first_present_span(self.text, ["快", "fast"]))
        elif "balanced" in self.lowered or "均衡" in self.text:
            self.add_field("run_profile", "balanced", 0.86, _first_present_span(self.text, ["均衡", "balanced"]))
        elif (
            "high accuracy" in self.lowered
            or "high-accuracy" in self.lowered
            or "thorough" in self.lowered
            or "高精度" in self.text
            or "全面" in self.text
        ):
            self.add_field(
                "run_profile",
                "high_accuracy",
                0.86,
                _first_present_span(self.text, ["高精度", "全面", "high accuracy", "thorough"]),
            )

    def add_safety_level(self) -> None:
        safety_match = re.search(r"\bS[0-2]\b", self.text, re.IGNORECASE)
        if safety_match:
            self.add_field("safety_level", safety_match.group(0).upper(), 0.9, safety_match.group(0))
        elif "低风险" in self.text or "low risk" in self.lowered:
            self.add_field("safety_level", "S1", 0.70, _first_present_span(self.text, ["低风险", "low risk"]))
        elif "安全" in self.text or "safe" in self.lowered:
            self.add_field("safety_level", "S1", 0.68, _first_present_span(self.text, ["安全", "safe"]))

    def add_plan_confirmation(self) -> None:
        if "无需确认计划" in self.text or "no plan confirmation" in self.lowered:
            self.add_field(
                "require_plan_confirm",
                False,
                0.92,
                _first_present_span(self.text, ["无需确认计划", "no plan confirmation"]),
            )
        elif "确认计划" in self.text or "confirm plan" in self.lowered:
            self.add_field(
                "require_plan_confirm",
                True,
                0.95,
                _first_present_span(self.text, ["确认计划", "confirm plan"]),
            )

    def add_tool_preferences(self) -> None:
        tool_preferences = _extract_tool_preferences(
            self.text,
            allowed_tool_ids=self.allowed_tool_ids,
        )
        if tool_preferences:
            self.add_field("tools_allowed", cast(JsonValue, tool_preferences), 0.76, ", ".join(tool_preferences))

    def add_goal_summary(self) -> None:
        if self.fields and self.design_intent and "goal_summary" not in self.fields:
            self.add_field("goal_summary", _goal_summary_from_text(self.text), 0.84, self.text.strip())

    def payload(self) -> JsonObject:
        return cast(
            JsonObject,
            {
                "fields": self.fields,
                "unmapped_text": [],
                "source_spans": cast(JsonValue, self.source_spans),
                "mode": "rule_extract",
            },
        )


def _first_present_span(text: str, needles: list[str]) -> str | None:
    lowered = text.lower()
    for needle in needles:
        if not needle:
            continue
        if needle in text or needle.lower() in lowered:
            return needle
    return None


def _goal_summary_from_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())[:2000]


def _extract_tool_preferences(
    text: str,
    *,
    allowed_tool_ids: AbstractSet[str],
) -> list[str]:
    lowered = text.lower()
    has_tool_cue = any(
        marker in lowered for marker in ("use", "prefer", "allowed", "tool")
    ) or any(marker in text for marker in ("使用", "优先", "允许", "工具"))
    if not has_tool_cue:
        return []
    return sorted(tool_id for tool_id in allowed_tool_ids if tool_id.lower() in lowered)
