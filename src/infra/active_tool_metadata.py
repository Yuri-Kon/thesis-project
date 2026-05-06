from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Literal

EvidenceRole = Literal[
    "cheap_validation",
    "core_generation",
    "high_cost_projection",
    "refinement",
    "objective_scoring",
]

DEFAULT_ACTIVE_TOOL_METADATA_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "tool_metadata"
    / "active_tool_metadata.json"
)

ACTIVE_TOOL_METADATA_VERSION = "active-tool-metadata.v1"

__all__ = [
    "ACTIVE_TOOL_METADATA_VERSION",
    "DEFAULT_ACTIVE_TOOL_METADATA_PATH",
    "ActiveToolMetadata",
    "build_high_cost_rules_from_metadata",
    "load_active_tool_metadata",
    "metadata_by_tool_id",
]


@dataclass(frozen=True)
class ActiveToolMetadata:
    """当前活跃工具的静态成本/风险画像。"""

    tool_id: str
    capability_id: str
    compute_cost_prior: float
    latency_cost_prior: float
    failure_impact_prior: float
    human_dependency_prior: float
    reliability_prior: float
    structural_risk_prior: float
    execution_risk_prior: float
    safety_risk_prior: float
    coupling_risk_prior: float
    high_cost_flag: bool
    evidence_role: EvidenceRole
    secondary_capability_ids: tuple[str, ...] = ()
    description: str = ""

    @property
    def capability_ids(self) -> tuple[str, ...]:
        """返回主能力与次级能力的稳定去重列表。"""
        ordered = [self.capability_id, *self.secondary_capability_ids]
        seen: set[str] = set()
        result: list[str] = []
        for item in ordered:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return tuple(result)

    @property
    def step_cost(self) -> float:
        """按设计公式计算单步标准成本。"""
        return round(
            0.40 * self.compute_cost_prior
            + 0.25 * self.latency_cost_prior
            + 0.20 * self.failure_impact_prior
            + 0.15 * self.human_dependency_prior,
            6,
        )

    @property
    def step_risk(self) -> float:
        """按设计公式计算单步标准风险。"""
        return round(
            0.45 * self.structural_risk_prior
            + 0.25 * self.execution_risk_prior
            + 0.20 * self.safety_risk_prior
            + 0.10 * self.coupling_risk_prior,
            6,
        )

    @property
    def is_evidence_layer(self) -> bool:
        """判断工具是否属于低成本证据层。"""
        return (
            not self.high_cost_flag
            and self.evidence_role == "cheap_validation"
            and self.step_cost <= 0.25
        )

    def to_dict(self) -> dict[str, Any]:
        """输出可审计 JSON 载荷。"""
        return {
            "tool_id": self.tool_id,
            "capability_id": self.capability_id,
            "secondary_capability_ids": list(self.secondary_capability_ids),
            "compute_cost_prior": self.compute_cost_prior,
            "latency_cost_prior": self.latency_cost_prior,
            "failure_impact_prior": self.failure_impact_prior,
            "human_dependency_prior": self.human_dependency_prior,
            "reliability_prior": self.reliability_prior,
            "structural_risk_prior": self.structural_risk_prior,
            "execution_risk_prior": self.execution_risk_prior,
            "safety_risk_prior": self.safety_risk_prior,
            "coupling_risk_prior": self.coupling_risk_prior,
            "high_cost_flag": self.high_cost_flag,
            "evidence_role": self.evidence_role,
            "step_cost": self.step_cost,
            "step_risk": self.step_risk,
            "is_evidence_layer": self.is_evidence_layer,
            "description": self.description,
        }


@lru_cache(maxsize=8)
def load_active_tool_metadata(
    path: Path | str = DEFAULT_ACTIVE_TOOL_METADATA_PATH,
) -> tuple[ActiveToolMetadata, ...]:
    """加载并校验活跃工具元数据画像。"""
    metadata_path = Path(path)
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    version = payload.get("schema_version")
    if version != ACTIVE_TOOL_METADATA_VERSION:
        raise ValueError(
            f"active tool metadata schema_version must be {ACTIVE_TOOL_METADATA_VERSION}"
        )
    tools = payload.get("tools")
    if not isinstance(tools, list) or not tools:
        raise ValueError("active tool metadata must contain non-empty tools")

    profiles: list[ActiveToolMetadata] = []
    seen: set[str] = set()
    for raw in tools:
        if not isinstance(raw, dict):
            raise ValueError("active tool metadata entries must be objects")
        profile = _parse_profile(raw)
        if profile.tool_id in seen:
            raise ValueError(f"duplicate active tool metadata: {profile.tool_id}")
        seen.add(profile.tool_id)
        profiles.append(profile)
    return tuple(profiles)


def metadata_by_tool_id(
    path: Path | str = DEFAULT_ACTIVE_TOOL_METADATA_PATH,
) -> dict[str, ActiveToolMetadata]:
    """按 tool_id 返回活跃工具元数据画像。"""
    return {profile.tool_id: profile for profile in load_active_tool_metadata(path)}


def build_high_cost_rules_from_metadata(
    profiles: Iterable[ActiveToolMetadata] | None = None,
) -> list[dict[str, Any]]:
    """从统一画像生成实验高代价规则。"""
    source_profiles = tuple(profiles or load_active_tool_metadata())
    high_cost_profiles = [profile for profile in source_profiles if profile.high_cost_flag]
    rules: list[dict[str, Any]] = []

    structure_tools = [
        profile for profile in high_cost_profiles if "structure_prediction" in profile.capability_ids
    ]
    if structure_tools:
        rules.append(
            _build_group_rule(
                rule_id="structure_mapping",
                label="结构映射",
                stage_ids=["S2"],
                profiles=structure_tools,
                rationale_prefix="结构预测调用通常消耗远程/重模型预算，是高代价主来源。",
            )
        )

    refinement_tools = [
        profile for profile in high_cost_profiles if "sequence_design" in profile.capability_ids
    ]
    if refinement_tools:
        rules.append(
            _build_group_rule(
                rule_id="structure_refinement",
                label="结构条件下的序列精修",
                stage_ids=["S4"],
                profiles=refinement_tools,
                rationale_prefix="ProteinMPNN 多轮采样与回放属于高暴露恢复环节。",
            )
        )

    grouped_tool_ids = {
        tool_id
        for rule in rules
        for tool_id in rule.get("tool_ids", [])
        if isinstance(tool_id, str)
    }
    for profile in high_cost_profiles:
        if profile.tool_id in grouped_tool_ids:
            continue
        rules.append(
            _build_group_rule(
                rule_id=f"active_tool_{profile.tool_id}_high_cost",
                label=f"{profile.tool_id} high-cost exposure",
                stage_ids=[],
                profiles=[profile],
                rationale_prefix="该工具由活跃工具画像标记为高代价。",
            )
        )
    return rules


def _build_group_rule(
    *,
    rule_id: str,
    label: str,
    stage_ids: list[str],
    profiles: Iterable[ActiveToolMetadata],
    rationale_prefix: str,
) -> dict[str, Any]:
    profile_list = list(profiles)
    capability_ids = sorted(
        {
            capability
            for profile in profile_list
            for capability in profile.capability_ids
        }
    )
    max_cost = max((profile.step_cost for profile in profile_list), default=0.0)
    max_risk = max((profile.step_risk for profile in profile_list), default=0.0)
    return {
        "rule_id": rule_id,
        "label": label,
        "stage_ids": stage_ids,
        "tool_ids": [profile.tool_id for profile in profile_list],
        "capability_ids": capability_ids,
        "cost_tier": "high" if max_cost >= 0.65 else "medium_high",
        "rationale": (
            f"{rationale_prefix} Derived from active-tool-metadata.v1: "
            f"max_step_cost={max_cost:.3f}, max_step_risk={max_risk:.3f}."
        ),
    }


def _parse_profile(raw: dict[str, Any]) -> ActiveToolMetadata:
    tool_id = _required_text(raw, "tool_id")
    capability_id = _required_text(raw, "capability_id")
    evidence_role = _required_text(raw, "evidence_role")
    allowed_roles = set(EvidenceRole.__args__)  # type: ignore[attr-defined]
    if evidence_role not in allowed_roles:
        raise ValueError(f"{tool_id}.evidence_role is invalid: {evidence_role}")
    secondary = raw.get("secondary_capability_ids") or []
    if not isinstance(secondary, list):
        raise ValueError(f"{tool_id}.secondary_capability_ids must be a list")
    secondary_capability_ids = tuple(
        str(item).strip() for item in secondary if isinstance(item, str) and item.strip()
    )
    high_cost_flag = raw.get("high_cost_flag")
    if not isinstance(high_cost_flag, bool):
        raise ValueError(f"{tool_id}.high_cost_flag must be boolean")
    return ActiveToolMetadata(
        tool_id=tool_id,
        capability_id=capability_id,
        compute_cost_prior=_unit_float(raw, "compute_cost_prior", tool_id),
        latency_cost_prior=_unit_float(raw, "latency_cost_prior", tool_id),
        failure_impact_prior=_unit_float(raw, "failure_impact_prior", tool_id),
        human_dependency_prior=_unit_float(raw, "human_dependency_prior", tool_id),
        reliability_prior=_unit_float(raw, "reliability_prior", tool_id),
        structural_risk_prior=_unit_float(raw, "structural_risk_prior", tool_id),
        execution_risk_prior=_unit_float(raw, "execution_risk_prior", tool_id),
        safety_risk_prior=_unit_float(raw, "safety_risk_prior", tool_id),
        coupling_risk_prior=_unit_float(raw, "coupling_risk_prior", tool_id),
        high_cost_flag=high_cost_flag,
        evidence_role=evidence_role,  # type: ignore[arg-type]
        secondary_capability_ids=secondary_capability_ids,
        description=str(raw.get("description") or ""),
    )


def _required_text(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _unit_float(raw: dict[str, Any], key: str, tool_id: str) -> float:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{tool_id}.{key} must be numeric")
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise ValueError(f"{tool_id}.{key} must be in [0, 1]")
    return parsed
