from src.agents.planner import ToolSpec
from src.llm.provider_payload_parser import ProviderPayloadParser


def _parser_registry():
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


def test_provider_payload_parser_repairs_stringified_steps_and_reference_variants():
    parser = ProviderPayloadParser(_parser_registry())
    payload = {
        "task_id": "task_001",
        "steps": (
            '[{"id":"step_1","tool":"protgpt2","inputs":{"goal":"design"},"metadata":{}},'
            '{"id":"step_2","tool":"openfold","inputs":{"sequence":"${step.1.sequence}"},"metadata":{}},'
            '{"id":"step_3","tool":"objective_ranker","inputs":{"candidates":"$CANDIDATES"},"metadata":{}},'
            '{"id":"step_4","tool":"biopython_qc","inputs":{"sequence":"auto","pdb_path":"<predicted_pdb>"},"metadata":{}}]'
        ),
        "constraints": "{}",
        "metadata": "{}",
    }

    result = parser.parse(payload, candidate_kind="plan")

    assert result.is_compliant
    assert isinstance(result.normalized_payload, dict)
    assert [step["id"] for step in result.normalized_payload["steps"]] == ["S1", "S2", "S3", "S4"]
    assert result.normalized_payload["steps"][1]["inputs"]["sequence"] == "S1.sequence"
    assert result.normalized_payload["steps"][2]["inputs"]["candidates"] == "S1.candidates"
    assert result.normalized_payload["steps"][3]["inputs"]["sequence"] == "S1.sequence"
    assert result.normalized_payload["steps"][3]["inputs"]["pdb_path"] == "S2.pdb_path"
    assert result.repairs


def test_provider_payload_parser_reports_unresolved_reference_tokens():
    parser = ProviderPayloadParser(_parser_registry())
    payload = {
        "task_id": "task_001",
        "steps": [
            {
                "id": "S1",
                "tool": "openfold",
                "inputs": {"sequence": "$STEP_9"},
                "metadata": {},
            }
        ],
        "constraints": {},
        "metadata": {},
    }

    result = parser.parse(payload, candidate_kind="plan")

    assert not result.is_compliant
    assert result.issues
    assert result.issues[0].code == "REFERENCE_SYNTAX_INVALID"
    assert result.issues[0].path == "$.steps[0].inputs.sequence"


def test_provider_payload_parser_normalizes_indexed_candidate_reference_for_sequence_input():
    parser = ProviderPayloadParser(_parser_registry())
    payload = {
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
                "inputs": {"sequence": "S1.candidates[0]"},
                "metadata": {},
            },
        ],
        "constraints": {},
        "metadata": {},
    }

    result = parser.parse(payload, candidate_kind="plan")

    assert result.is_compliant
    assert result.normalized_payload["steps"][1]["inputs"]["sequence"] == "S1.sequence"
    assert any(repair.path == "$.steps[1].inputs.sequence" for repair in result.repairs)
