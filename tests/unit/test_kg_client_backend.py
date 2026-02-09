from src.kg.kg_client import (
    find_tools_by_backend,
    find_tools_by_capability,
    load_tool_kg,
)


def test_find_tools_by_capability_includes_nim_esmfold() -> None:
    tools = find_tools_by_capability("structure_prediction")
    tool_ids = {tool["id"] for tool in tools}

    assert "esmfold" in tool_ids
    assert "nim_esmfold" in tool_ids


def test_find_tools_by_backend_remote_model_service() -> None:
    tools = find_tools_by_backend("remote_model_service", "nvidia_nim")
    tool_ids = {tool["id"] for tool in tools}

    assert tool_ids == {"nim_esmfold"}


def test_find_tools_by_backend_plm_rest() -> None:
    tools = find_tools_by_backend("remote_model_service", "plm_rest")
    tool_ids = {tool["id"] for tool in tools}

    assert tool_ids == {"protgpt2"}


def test_find_tools_by_backend_nextflow() -> None:
    tools = find_tools_by_backend("nextflow")
    tool_ids = {tool["id"] for tool in tools}

    assert "esmfold" in tool_ids


def test_mpnn_to_nim_esmfold_chain_is_compatible() -> None:
    kg = load_tool_kg()
    tools = {tool["id"]: tool for tool in kg["tools"]}

    mpnn_outputs = set(tools["protein_mpnn"]["io"]["outputs"].keys())
    nim_inputs = set(tools["nim_esmfold"]["io"]["inputs"].keys())

    assert nim_inputs.issubset(mpnn_outputs)


def test_protgpt2_has_sequence_generation_capability() -> None:
    tools = find_tools_by_capability("sequence_generation")
    tool_ids = {tool["id"] for tool in tools}

    assert "protgpt2" in tool_ids
