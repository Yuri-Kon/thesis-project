from src.kg.kg_client import load_tool_kg


def test_kg_includes_plm_and_design_capabilities() -> None:
    kg = load_tool_kg()
    tool_ids = {tool["id"] for tool in kg["tools"]}
    capability_ids = {cap["capability_id"] for cap in kg["capabilities"]}
    io_type_ids = {io_type["io_type_id"] for io_type in kg["io_types"]}

    assert "protein_mpnn" in tool_ids
    assert "protgpt2" in tool_ids
    assert "alphafold" in tool_ids
    assert "openfold" in tool_ids
    assert "biopython_qc" in tool_ids
    assert "mmseqs2" in tool_ids
    assert "blastp" in tool_ids
    assert "dssp" in tool_ids
    assert "sequence_design" in capability_ids
    assert "sequence_generation" in capability_ids
    assert "quality_qc" in capability_ids
    assert "objective_scoring" in capability_ids
    assert "sequence_similarity_search" in capability_ids
    assert "secondary_structure_annotation" in capability_ids
    assert "structure_to_sequence" in io_type_ids
    assert "goal_to_sequence_candidates" in io_type_ids
    assert "sequence_structure_to_qc_metrics" in io_type_ids
    assert "sequence_to_similarity_hits" in io_type_ids
    assert "structure_to_secondary_structure" in io_type_ids


def test_generation_to_prediction_chain_is_compatible() -> None:
    kg = load_tool_kg()
    tools = {tool["id"]: tool for tool in kg["tools"]}

    protgpt2 = tools["protgpt2"]
    esmfold = tools["esmfold"]

    generation_outputs = set(protgpt2["io"]["outputs"].keys())
    esmfold_inputs = set(esmfold["io"]["inputs"].keys())

    assert esmfold_inputs.issubset(generation_outputs)


def test_biopython_qc_accepts_single_structure_inputs() -> None:
    kg = load_tool_kg()
    tools = {tool["id"]: tool for tool in kg["tools"]}

    biopython_qc = tools["biopython_qc"]
    qc_inputs = set(biopython_qc["io"]["inputs"].keys())

    assert qc_inputs == {"sequence", "pdb_path"}
