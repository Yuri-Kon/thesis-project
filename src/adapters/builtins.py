from __future__ import annotations

import os

from src.adapters.alphafold_adapter import AlphaFold2Adapter
from src.adapters.autodock_vina_adapter import AutoDockVinaAdapter
from src.adapters.blastp_adapter import BlastPAdapter
from src.adapters.biopython_qc_adapter import BioPythonQCAdapter
from src.adapters.dssp_adapter import DSSPAdapter
from src.adapters.dummy_adapter import DummyToolAdapter
from src.adapters.esmfold_adapter import ESMFoldAdapter
from src.adapters.foldseek_adapter import FoldseekAdapter
from src.adapters.interproscan_adapter import InterProScanAdapter
from src.adapters.mda_analysis_adapter import MDAnalysisAdapter
from src.adapters.mmseqs2_adapter import MMseqs2Adapter
from src.adapters.nim_adapter import NIMESMFoldAdapter
from src.adapters.objective_ranker_adapter import ObjectiveRankerAdapter
from src.adapters.openfold_adapter import OpenFold2Adapter, OpenFold3Adapter
from src.adapters.protein_mpnn_adapter import ProteinMPNNAdapter
from src.adapters.protgpt2_adapter import ProtGPT2Adapter
from src.adapters.registry import get_adapter, register_adapter
from src.engines.provider_config import get_provider_config
from src.tools.visualization.adapter import VisualizationToolAdapter

__all__ = ["ensure_builtin_adapters"]


_BUILTIN_TOOL_IDS = (
    "dummy_tool",
    "dummy_tool_alt",
    "dummy_tool_safe",
)


def ensure_builtin_adapters() -> None:
    """注册内置适配器，供本地最小闭环使用"""
    for tool_id in _BUILTIN_TOOL_IDS:
        try:
            get_adapter(tool_id)
        except KeyError:
            register_adapter(DummyToolAdapter(tool_id))
    try:
        get_adapter(VisualizationToolAdapter.tool_id)
    except KeyError:
        register_adapter(VisualizationToolAdapter())
    try:
        get_adapter(ESMFoldAdapter.tool_id)
    except KeyError:
        register_adapter(ESMFoldAdapter())
    nim_api_key = os.getenv("NIM_API_KEY")
    if nim_api_key:
        try:
            get_adapter(NIMESMFoldAdapter.tool_id)
        except KeyError:
            register_adapter(NIMESMFoldAdapter())
        try:
            get_adapter(AlphaFold2Adapter.tool_id)
        except KeyError:
            register_adapter(AlphaFold2Adapter())
    openfold_rest_available = bool(os.getenv("OPENFOLD3_REST_BASE_URL")) or bool(
        os.getenv("OPENFOLD2_REST_BASE_URL")
    )
    if not openfold_rest_available:
        try:
            provider_cfg = get_provider_config("openfold3_rest")
            openfold_rest_available = bool(provider_cfg.base_url)
        except KeyError:
            try:
                provider_cfg = get_provider_config("openfold2_rest")
                openfold_rest_available = bool(provider_cfg.base_url)
            except KeyError:
                openfold_rest_available = False
    if nim_api_key or openfold_rest_available:
        try:
            get_adapter(OpenFold3Adapter.tool_id)
        except KeyError:
            register_adapter(OpenFold3Adapter())
        try:
            get_adapter(OpenFold2Adapter.tool_id)
        except KeyError:
            register_adapter(OpenFold2Adapter())
    try:
        get_adapter(ProteinMPNNAdapter.tool_id)
    except KeyError:
        register_adapter(ProteinMPNNAdapter())
    try:
        get_adapter(ProtGPT2Adapter.tool_id)
    except KeyError:
        register_adapter(ProtGPT2Adapter())
    try:
        get_adapter(BioPythonQCAdapter.tool_id)
    except KeyError:
        register_adapter(BioPythonQCAdapter())
    try:
        get_adapter(MMseqs2Adapter.tool_id)
    except KeyError:
        register_adapter(MMseqs2Adapter())
    try:
        get_adapter(BlastPAdapter.tool_id)
    except KeyError:
        register_adapter(BlastPAdapter())
    try:
        get_adapter(DSSPAdapter.tool_id)
    except KeyError:
        register_adapter(DSSPAdapter())
    try:
        get_adapter(ObjectiveRankerAdapter.tool_id)
    except KeyError:
        register_adapter(ObjectiveRankerAdapter())
    try:
        get_adapter(FoldseekAdapter.tool_id)
    except KeyError:
        register_adapter(FoldseekAdapter())
    try:
        get_adapter(InterProScanAdapter.tool_id)
    except KeyError:
        register_adapter(InterProScanAdapter())
    try:
        get_adapter(MDAnalysisAdapter.tool_id)
    except KeyError:
        register_adapter(MDAnalysisAdapter())
    try:
        get_adapter(AutoDockVinaAdapter.tool_id)
    except KeyError:
        register_adapter(AutoDockVinaAdapter())
