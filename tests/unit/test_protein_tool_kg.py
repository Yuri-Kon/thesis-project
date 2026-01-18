from src.kg.kg_client import load_tool_kg


def test_kg_includes_protein_mpnn_and_design_capability() -> None:
    kg = load_tool_kg()
    tool_ids = {tool["id"] for tool in kg["tools"]}
    capability_ids = {cap["capability_id"] for cap in kg["capabilities"]}
    io_type_ids = {io_type["io_type_id"] for io_type in kg["io_types"]}

    assert "protein_mpnn" in tool_ids
    assert "sequence_design" in capability_ids
    assert "structure_to_sequence" in io_type_ids


def test_design_to_prediction_chain_is_compatible() -> None:
    kg = load_tool_kg()
    tools = {tool["id"]: tool for tool in kg["tools"]}

    mpnn = tools["protein_mpnn"]
    esmfold = tools["esmfold"]

    mpnn_outputs = set(mpnn["io"]["outputs"].keys())
    esmfold_inputs = set(esmfold["io"]["inputs"].keys())

    assert esmfold_inputs.issubset(mpnn_outputs)
