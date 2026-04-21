from types import SimpleNamespace

import pytest

from src.agents.planner import ToolSpec
import src.llm.anthropic_messages_provider as anthropic_provider_module
from src.llm.anthropic_messages_provider import AnthropicMessagesProvider
from src.llm.base_llm_provider import ProviderConfig
from src.llm.provider_payload_parser import ProviderPayloadValidationError
from src.models.contracts import PatchRequest, Plan, PlanStep, ProteinDesignTask, ReplanRequest, StepResult, now_iso
from src.models.validation import CandidateExecutionIssue, CandidateExecutionValidationError


def _sample_registry():
    return [
        ToolSpec(
            id="protgpt2",
            capabilities=("sequence_generation",),
            inputs=("goal",),
            outputs=("sequence", "candidates"),
            cost=1,
            safety_level=0,
        ),
        ToolSpec(
            id="esmfold",
            capabilities=("structure_prediction",),
            inputs=("sequence",),
            outputs=("pdb_path",),
            cost=1,
            safety_level=0,
        ),
        ToolSpec(
            id="protein_mpnn",
            capabilities=("sequence_redesign",),
            inputs=("pdb_path",),
            outputs=("sequence",),
            cost=1,
            safety_level=0,
        ),
        ToolSpec(
            id="openfold",
            capabilities=("structure_prediction",),
            inputs=("sequence",),
            outputs=("pdb_path", "structure_results"),
            cost=1,
            safety_level=0,
        ),
        ToolSpec(
            id="objective_ranker",
            capabilities=("ranking",),
            inputs=("candidates",),
            outputs=("score_table", "top_k"),
            cost=1,
            safety_level=0,
        ),
        ToolSpec(
            id="biopython_qc",
            capabilities=("quality_control",),
            inputs=("sequence", "pdb_path"),
            outputs=("qc_metrics",),
            cost=1,
            safety_level=0,
        ),
    ]


@pytest.fixture(autouse=True)
def _stub_candidate_validation(monkeypatch):
    monkeypatch.setattr(
        anthropic_provider_module,
        "validate_plan_executability",
        lambda plan, task: None,
    )


def _sample_task():
    return ProteinDesignTask(
        task_id="task_001",
        goal="design a stable protein",
        constraints={},
        metadata={},
    )


def _sample_patch_request() -> PatchRequest:
    plan = Plan(
        task_id="task_patch",
        steps=[PlanStep(id="S1", tool="esmfold", inputs={"sequence": "AAA"}, metadata={})],
        constraints={},
        metadata={},
    )
    result = StepResult(
        task_id="task_patch",
        step_id="S1",
        tool="esmfold",
        status="failed",
        failure_type="retryable",
        error_message="boom",
        error_details={},
        outputs={},
        metrics={},
        risk_flags=[],
        logs_path=None,
        timestamp=now_iso(),
    )
    return PatchRequest(
        task_id="task_patch",
        original_plan=plan,
        context_step_results=[result],
        safety_events=[],
        reason="retry exhausted",
    )


def _sample_replan_request() -> ReplanRequest:
    plan = Plan(
        task_id="task_replan",
        steps=[PlanStep(id="S1", tool="esmfold", inputs={"sequence": "AAA"}, metadata={})],
        constraints={},
        metadata={},
    )
    return ReplanRequest(
        task_id="task_replan",
        original_plan=plan,
        failed_steps=["S1"],
        safety_events=[],
        reason="patch_failed",
    )


def _fake_response(payload):
    return SimpleNamespace(
        model_dump=lambda mode="python": payload,
    )


def test_anthropic_provider_generates_plan_via_tool_use(monkeypatch):
    calls = {}

    class FakeMessages:
        def create(self, **kwargs):
            calls["kwargs"] = kwargs
            return _fake_response(
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "emit_plan",
                            "input": {
                                "task_id": "task_001",
                                "steps": [
                                    {"id": "S1", "tool": "esmfold", "inputs": {"sequence": "AAA"}, "metadata": {}}
                                ],
                                "constraints": {},
                                "metadata": {},
                            },
                        }
                    ]
                }
            )

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            calls["api_key"] = api_key
            calls["base_url"] = base_url
            calls["timeout"] = timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(
        ProviderConfig(
            model_name="glm-5",
            api_key="secret",
            anthropic_version="2023-06-01",
        ),
        endpoint="https://open.bigmodel.cn/api/anthropic",
    )

    plan = provider.call_planner(_sample_task(), _sample_registry())

    assert plan["steps"][0]["tool"] == "esmfold"
    assert plan["metadata"]["provider"] == "anthropic_messages"
    assert calls["base_url"] == "https://open.bigmodel.cn/api/anthropic"
    assert calls["api_key"] == "secret"
    assert calls["kwargs"]["tool_choice"] == {"type": "tool", "name": "emit_plan"}
    assert calls["kwargs"]["extra_headers"]["anthropic-version"] == "2023-06-01"


def test_anthropic_provider_generates_two_stage_plan_when_configured(monkeypatch):
    calls = {"tool_names": [], "prompts": []}
    payloads = {
        "emit_plan_skeleton": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_plan_skeleton",
                    "input": {
                        "task_id": "task_001",
                        "steps": [
                            {"id": "1", "tool": "protgpt2", "metadata": {}},
                            {"id": "2", "tool": "openfold", "metadata": {}},
                        ],
                        "constraints": {},
                        "metadata": {},
                    },
                }
            ]
        },
        "emit_plan": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_plan",
                    "input": {
                        "task_id": "task_001",
                        "steps": [
                            {
                                "id": "S1",
                                "tool": "protgpt2",
                                "inputs": {"goal": "design a stable protein"},
                                "metadata": {},
                            },
                            {
                                "id": "S2",
                                "tool": "openfold",
                                "inputs": {"sequence": "S1.sequence"},
                                "metadata": {},
                            },
                        ],
                        "constraints": {},
                        "metadata": {},
                    },
                }
            ]
        },
    }

    class FakeMessages:
        def create(self, **kwargs):
            tool_name = kwargs["tools"][0]["name"]
            calls["tool_names"].append(tool_name)
            calls["prompts"].append(kwargs["messages"][0]["content"])
            return _fake_response(payloads[tool_name])

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(
        ProviderConfig(
            model_name="MiniMax-M2.7",
            api_key="secret",
            tool_strategy="two_stage_plan",
        )
    )

    plan = provider.call_planner(_sample_task(), _sample_registry())

    assert calls["tool_names"] == ["emit_plan_skeleton", "emit_plan"]
    assert "已确认 PlanSkeleton" in calls["prompts"][1]
    assert [step["tool"] for step in plan["steps"]] == ["protgpt2", "openfold"]
    assert plan["steps"][0]["id"] == "S1"
    assert plan["metadata"]["provider_generation_mode"] == "two_stage_plan"
    assert plan["metadata"]["provider_plan_skeleton"]["step_count"] == 2


def test_anthropic_provider_repairs_skeleton_with_inputs(monkeypatch):
    calls = {"tool_names": [], "prompts": []}
    skeleton_payloads = [
        {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_plan_skeleton",
                    "input": {
                        "task_id": "task_001",
                        "steps": [
                            {
                                "id": "S1",
                                "tool": "protgpt2",
                                "inputs": {"goal": "design"},
                                "metadata": {},
                            }
                        ],
                        "constraints": {},
                        "metadata": {},
                    },
                }
            ]
        },
        {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_plan_skeleton",
                    "input": {
                        "task_id": "task_001",
                        "steps": [{"id": "S1", "tool": "protgpt2", "metadata": {}}],
                        "constraints": {},
                        "metadata": {},
                    },
                }
            ]
        },
    ]

    class FakeMessages:
        def __init__(self):
            self.skeleton_count = 0

        def create(self, **kwargs):
            tool_name = kwargs["tools"][0]["name"]
            calls["tool_names"].append(tool_name)
            calls["prompts"].append(kwargs["messages"][0]["content"])
            if tool_name == "emit_plan_skeleton":
                index = min(self.skeleton_count, len(skeleton_payloads) - 1)
                self.skeleton_count += 1
                return _fake_response(skeleton_payloads[index])
            return _fake_response(
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "emit_plan",
                            "input": {
                                "task_id": "task_001",
                                "steps": [
                                    {
                                        "id": "S1",
                                        "tool": "protgpt2",
                                        "inputs": {"goal": "design"},
                                        "metadata": {},
                                    }
                                ],
                                "constraints": {},
                                "metadata": {},
                            },
                        }
                    ]
                }
            )

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(
        ProviderConfig(
            model_name="MiniMax-M2.7",
            api_key="secret",
            tool_strategy="two_stage_plan",
        )
    )

    plan = provider.call_planner(_sample_task(), _sample_registry())

    assert calls["tool_names"] == [
        "emit_plan_skeleton",
        "emit_plan_skeleton",
        "emit_plan",
    ]
    assert "失败分类: SCHEMA_INVALID" in calls["prompts"][1]
    assert plan["steps"][0]["tool"] == "protgpt2"


def test_anthropic_provider_repairs_two_stage_plan_when_skeleton_mismatches(monkeypatch):
    calls = {"tool_names": [], "prompts": []}
    final_payloads = [
        {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_plan",
                    "input": {
                        "task_id": "task_001",
                        "steps": [
                            {
                                "id": "S1",
                                "tool": "protgpt2",
                                "inputs": {"goal": "design"},
                                "metadata": {},
                            },
                            {
                                "id": "S2",
                                "tool": "esmfold",
                                "inputs": {"sequence": "S1.sequence"},
                                "metadata": {},
                            },
                        ],
                        "constraints": {},
                        "metadata": {},
                    },
                }
            ]
        },
        {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_plan",
                    "input": {
                        "task_id": "task_001",
                        "steps": [
                            {
                                "id": "S1",
                                "tool": "protgpt2",
                                "inputs": {"goal": "design"},
                                "metadata": {},
                            },
                            {
                                "id": "S2",
                                "tool": "openfold",
                                "inputs": {"sequence": "S1.sequence"},
                                "metadata": {},
                            },
                        ],
                        "constraints": {},
                        "metadata": {},
                    },
                }
            ]
        },
    ]

    class FakeMessages:
        def __init__(self):
            self.final_count = 0

        def create(self, **kwargs):
            tool_name = kwargs["tools"][0]["name"]
            calls["tool_names"].append(tool_name)
            calls["prompts"].append(kwargs["messages"][0]["content"])
            if tool_name == "emit_plan_skeleton":
                return _fake_response(
                    {
                        "content": [
                            {
                                "type": "tool_use",
                                "name": "emit_plan_skeleton",
                                "input": {
                                    "task_id": "task_001",
                                    "steps": [
                                        {"id": "S1", "tool": "protgpt2", "metadata": {}},
                                        {"id": "S2", "tool": "openfold", "metadata": {}},
                                    ],
                                    "constraints": {},
                                    "metadata": {},
                                },
                            }
                        ]
                    }
                )
            index = min(self.final_count, len(final_payloads) - 1)
            self.final_count += 1
            return _fake_response(final_payloads[index])

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(
        ProviderConfig(
            model_name="MiniMax-M2.7",
            api_key="secret",
            tool_strategy="two_stage_plan",
        )
    )

    plan = provider.call_planner(_sample_task(), _sample_registry())

    assert calls["tool_names"] == ["emit_plan_skeleton", "emit_plan", "emit_plan"]
    assert "final Plan tool must match PlanSkeleton" in calls["prompts"][2]
    assert plan["steps"][1]["tool"] == "openfold"
    assert plan["metadata"]["provider_validation"]["repair_attempts"] == 1


def test_anthropic_provider_generates_patch_and_replan(monkeypatch):
    payloads = {
        "emit_patch": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_patch",
                    "input": {
                        "task_id": "task_patch",
                        "operations": [
                            {
                                "op": "replace_step",
                                "target": "S1",
                                "step": {
                                    "tool": "protein_mpnn",
                                    "inputs": {"pdb_path": "S1.pdb_path"},
                                    "metadata": {},
                                },
                            }
                        ],
                        "metadata": {"recovery_layer": "tool_level", "reason": "swap"},
                    },
                }
            ]
        },
        "emit_replan": {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_replan",
                    "input": {
                        "task_id": "task_replan",
                        "steps": [
                            {"id": "S1", "tool": "protein_mpnn", "inputs": {"pdb_path": "input.pdb"}, "metadata": {}}
                        ],
                        "constraints": {},
                        "metadata": {"replan_mode": "suffix_replan"},
                    },
                }
            ]
        },
    }

    class FakeMessages:
        def create(self, **kwargs):
            tool_name = kwargs["tools"][0]["name"]
            return _fake_response(payloads[tool_name])

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(ProviderConfig(model_name="glm-5", api_key="secret"))

    patch = provider.call_patch(_sample_patch_request(), _sample_registry())
    replan = provider.call_replan(_sample_replan_request(), _sample_registry())

    assert patch is not None
    assert patch["metadata"]["planning_mode"] == "patch"
    assert patch["operations"][0]["op"] == "replace_step"
    assert replan is not None
    assert replan["metadata"]["planning_mode"] == "replan"
    assert replan["steps"][0]["tool"] == "protein_mpnn"


def test_anthropic_provider_repairs_stringified_steps_payload(monkeypatch):
    class FakeMessages:
        def create(self, **kwargs):
            del kwargs
            return _fake_response(
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "emit_plan",
                            "input": {
                                "task_id": "task_001",
                                "steps": (
                                    '[{""id"": ""S1"", ""tool"": ""esmfold"", '
                                    '""inputs"": {""sequence"": ""AAA""}, ""metadata"": {}}]'
                                ),
                                "constraints": "{}",
                                "metadata": "{}",
                            },
                        }
                    ]
                }
            )

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(
        ProviderConfig(model_name="glm-5", api_key="secret")
    )

    plan = provider.call_planner(_sample_task(), _sample_registry())

    assert isinstance(plan["steps"], list)
    assert plan["steps"][0]["id"] == "S1"
    assert plan["steps"][0]["inputs"]["sequence"] == "AAA"


def test_anthropic_provider_repairs_stringified_nested_inputs(monkeypatch):
    class FakeMessages:
        def create(self, **kwargs):
            del kwargs
            return _fake_response(
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "emit_plan",
                            "input": {
                                "task_id": "task_001",
                                "steps": [
                                    {
                                        "id": "S1",
                                        "tool": "protein_mpnn",
                                        "inputs": {
                                            "candidates": '[{"sequence":"AAA","score":0.9}]',
                                        },
                                        "metadata": {},
                                    }
                                ],
                                "constraints": {},
                                "metadata": {},
                            },
                        }
                    ]
                }
            )

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(
        ProviderConfig(model_name="glm-5", api_key="secret")
    )

    plan = provider.call_planner(_sample_task(), _sample_registry())

    assert isinstance(plan["steps"][0]["inputs"]["candidates"], list)
    assert plan["steps"][0]["inputs"]["candidates"][0]["sequence"] == "AAA"


def test_anthropic_provider_normalizes_tool_output_references_and_step_ids(monkeypatch):
    class FakeMessages:
        def create(self, **kwargs):
            del kwargs
            return _fake_response(
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "emit_plan",
                            "input": {
                                "task_id": "task_001",
                                "steps": [
                                    {
                                        "id": "1",
                                        "tool": "protein_mpnn",
                                        "inputs": {"goal": "design"},
                                        "metadata": {},
                                    },
                                    {
                                        "id": "2",
                                        "tool": "openfold",
                                        "inputs": {
                                            "sequence": "protein_mpnn.output.sequence",
                                        },
                                        "metadata": {},
                                    },
                                    {
                                        "id": "3",
                                        "tool": "biopython_qc",
                                        "inputs": {
                                            "sequence": "protein_mpnn.output.sequence",
                                            "pdb_path": "openfold.output.pdb_path",
                                        },
                                        "metadata": {},
                                    },
                                ],
                                "constraints": {},
                                "metadata": {},
                            },
                        }
                    ]
                }
            )

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(
        ProviderConfig(model_name="glm-5", api_key="secret")
    )

    plan = provider.call_planner(_sample_task(), _sample_registry())

    assert [step["id"] for step in plan["steps"]] == ["S1", "S2", "S3"]
    assert plan["steps"][1]["inputs"]["sequence"] == "S1.sequence"
    assert plan["steps"][2]["inputs"]["sequence"] == "S1.sequence"
    assert plan["steps"][2]["inputs"]["pdb_path"] == "S2.pdb_path"


def test_anthropic_provider_normalizes_candidate_references(monkeypatch):
    class FakeMessages:
        def create(self, **kwargs):
            del kwargs
            return _fake_response(
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "emit_plan",
                            "input": {
                                "task_id": "task_001",
                                "steps": [
                                    {
                                        "id": "step_1",
                                        "tool": "protein_mpnn",
                                        "inputs": {"goal": "design"},
                                        "metadata": {},
                                    },
                                    {
                                        "id": "step_2",
                                        "tool": "objective_ranker",
                                        "inputs": {
                                            "candidates": "protein_mpnn.output.candidates",
                                            "top_k": 1,
                                        },
                                        "metadata": {},
                                    },
                                ],
                                "constraints": {},
                                "metadata": {},
                            },
                        }
                    ]
                }
            )

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(
        ProviderConfig(model_name="glm-5", api_key="secret")
    )

    plan = provider.call_planner(_sample_task(), _sample_registry())

    assert [step["id"] for step in plan["steps"]] == ["S1", "S2"]
    assert plan["steps"][1]["inputs"]["candidates"] == "S1.candidates"


def test_anthropic_provider_normalizes_placeholder_references(monkeypatch):
    class FakeMessages:
        def create(self, **kwargs):
            del kwargs
            return _fake_response(
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "emit_plan",
                            "input": {
                                "task_id": "task_001",
                                "steps": [
                                    {
                                        "id": "1",
                                        "tool": "protein_mpnn",
                                        "inputs": {"goal": "design"},
                                        "metadata": {},
                                    },
                                    {
                                        "id": "2",
                                        "tool": "openfold",
                                        "inputs": {"sequence": "<from_step_1>"},
                                        "metadata": {},
                                    },
                                    {
                                        "id": "3",
                                        "tool": "objective_ranker",
                                        "inputs": {
                                            "candidates": "<from_step_1_candidates>",
                                            "top_k": 1,
                                        },
                                        "metadata": {},
                                    },
                                    {
                                        "id": "4",
                                        "tool": "biopython_qc",
                                        "inputs": {
                                            "pdb_path": "<from_step_2>",
                                            "sequence": "<from_step_1>",
                                        },
                                        "metadata": {},
                                    },
                                ],
                                "constraints": {},
                                "metadata": {},
                            },
                        }
                    ]
                }
            )

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(
        ProviderConfig(model_name="glm-5", api_key="secret")
    )

    plan = provider.call_planner(_sample_task(), _sample_registry())

    assert plan["steps"][1]["inputs"]["sequence"] == "S1.sequence"
    assert plan["steps"][2]["inputs"]["candidates"] == "S1.candidates"
    assert plan["steps"][3]["inputs"]["pdb_path"] == "S2.pdb_path"
    assert plan["steps"][3]["inputs"]["sequence"] == "S1.sequence"


def test_anthropic_provider_rewrites_semantically_wrong_reference_fields(monkeypatch):
    class FakeMessages:
        def create(self, **kwargs):
            del kwargs
            return _fake_response(
                {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "emit_plan",
                            "input": {
                                "task_id": "task_001",
                                "steps": [
                                    {
                                        "id": "S1",
                                        "tool": "protgpt2",
                                        "inputs": {"goal": "design"},
                                        "metadata": {},
                                    },
                                    {
                                        "id": "S2",
                                        "tool": "openfold",
                                        "inputs": {"sequence": "S1.candidates"},
                                        "metadata": {},
                                    },
                                    {
                                        "id": "S3",
                                        "tool": "objective_ranker",
                                        "inputs": {"candidates": "S1.sequence"},
                                        "metadata": {},
                                    },
                                ],
                                "constraints": {},
                                "metadata": {},
                            },
                        }
                    ]
                }
            )

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(
        ProviderConfig(model_name="glm-5", api_key="secret")
    )

    plan = provider.call_planner(_sample_task(), _sample_registry())

    assert plan["steps"][1]["inputs"]["sequence"] == "S1.sequence"
    assert plan["steps"][2]["inputs"]["candidates"] == "S1.candidates"


def test_anthropic_provider_retries_plan_when_syntax_invalid(monkeypatch):
    calls = {"count": 0, "prompts": []}
    payloads = [
        {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_plan",
                    "input": {
                        "task_id": "task_001",
                        "steps": [
                            {
                                "id": "S1",
                                "tool": "esmfold",
                                "inputs": {"sequence": "AAA"},
                                "metadata": {},
                            },
                            {
                                "id": "S2",
                                "tool": "protein_mpnn",
                                "inputs": {"pdb_path": "$STEP_9"},
                                "metadata": {},
                            },
                        ],
                        "constraints": {},
                        "metadata": {},
                    },
                }
            ]
        },
        {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_plan",
                    "input": {
                        "task_id": "task_001",
                        "steps": [
                            {
                                "id": "S1",
                                "tool": "esmfold",
                                "inputs": {"sequence": "AAA"},
                                "metadata": {},
                            },
                            {
                                "id": "S2",
                                "tool": "protein_mpnn",
                                "inputs": {"pdb_path": "S1.pdb_path"},
                                "metadata": {},
                            },
                        ],
                        "constraints": {},
                        "metadata": {},
                    },
                }
            ]
        },
    ]

    class FakeMessages:
        def create(self, **kwargs):
            calls["prompts"].append(kwargs["messages"][0]["content"])
            index = min(calls["count"], len(payloads) - 1)
            calls["count"] += 1
            return _fake_response(payloads[index])

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(
        ProviderConfig(model_name="glm-5", api_key="secret")
    )

    plan = provider.call_planner(_sample_task(), _sample_registry())

    assert calls["count"] == 2
    assert "失败分类: SYNTAX_INVALID" in calls["prompts"][1]
    assert plan["steps"][1]["inputs"]["pdb_path"] == "S1.pdb_path"
    assert plan["metadata"]["provider_validation"]["repair_attempts"] == 1


def test_anthropic_provider_retries_patch_when_executability_invalid(monkeypatch):
    calls = {"count": 0, "prompts": []}
    payloads = [
        {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_patch",
                    "input": {
                        "task_id": "task_patch",
                        "operations": [
                            {
                                "op": "replace_step",
                                "target": "S1",
                                "step": {
                                    "tool": "protein_mpnn",
                                    "inputs": {},
                                    "metadata": {},
                                },
                            }
                        ],
                        "metadata": {},
                    },
                }
            ]
        },
        {
            "content": [
                {
                    "type": "tool_use",
                    "name": "emit_patch",
                    "input": {
                        "task_id": "task_patch",
                        "operations": [
                            {
                                "op": "replace_step",
                                "target": "S1",
                                "step": {
                                    "tool": "protein_mpnn",
                                    "inputs": {"pdb_path": "input.pdb"},
                                    "metadata": {},
                                },
                            }
                        ],
                        "metadata": {},
                    },
                }
            ]
        },
    ]

    def fake_validate(plan, task):
        del task
        step = plan.steps[0]
        if step.tool == "protein_mpnn" and "pdb_path" not in step.inputs:
            raise CandidateExecutionValidationError(
                [
                    CandidateExecutionIssue(
                        code="CANDIDATE_PARAMS_INVALID",
                        message="required input 'pdb_path' is missing",
                        step_id=step.id,
                        tool_id=step.tool,
                    )
                ]
            )

    class FakeMessages:
        def create(self, **kwargs):
            calls["prompts"].append(kwargs["messages"][0]["content"])
            index = min(calls["count"], len(payloads) - 1)
            calls["count"] += 1
            return _fake_response(payloads[index])

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    monkeypatch.setattr(
        anthropic_provider_module,
        "validate_plan_executability",
        fake_validate,
    )
    provider = AnthropicMessagesProvider(
        ProviderConfig(model_name="glm-5", api_key="secret")
    )

    patch = provider.call_patch(_sample_patch_request(), _sample_registry())

    assert patch is not None
    assert calls["count"] == 2
    assert "失败分类: EXECUTABILITY_INVALID" in calls["prompts"][1]
    assert patch["operations"][0]["step"]["inputs"]["pdb_path"] == "input.pdb"
    assert patch["metadata"]["provider_validation"]["repair_attempts"] == 1


def test_anthropic_provider_raises_typed_error_after_retry_exhausted(monkeypatch):
    calls = {"count": 0}
    payload = {
        "content": [
            {
                "type": "tool_use",
                "name": "emit_replan",
                "input": {
                    "task_id": "task_replan",
                    "steps": [
                        {
                            "id": "S1",
                            "tool": "protein_mpnn",
                            "inputs": {"pdb_path": "$STEP_9"},
                            "metadata": {},
                        }
                    ],
                    "constraints": {},
                    "metadata": {},
                },
            }
        ]
    }

    class FakeMessages:
        def create(self, **kwargs):
            del kwargs
            calls["count"] += 1
            return _fake_response(payload)

    class FakeAnthropic:
        def __init__(self, *, api_key, base_url, timeout):
            del api_key, base_url, timeout
            self.messages = FakeMessages()

    monkeypatch.setattr(anthropic_provider_module, "Anthropic", FakeAnthropic)
    provider = AnthropicMessagesProvider(
        ProviderConfig(model_name="glm-5", api_key="secret")
    )

    with pytest.raises(ProviderPayloadValidationError) as exc_info:
        provider.call_replan(_sample_replan_request(), _sample_registry())

    assert calls["count"] == 3
    assert exc_info.value.failure_type == "SYNTAX_INVALID"
    assert exc_info.value.candidate_kind == "replan"
    assert exc_info.value.attempts == 3
