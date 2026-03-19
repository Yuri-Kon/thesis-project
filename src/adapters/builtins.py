from __future__ import annotations

import os

from src.adapters.alphafold_adapter import AlphaFold2Adapter
from src.adapters.biopython_qc_adapter import BioPythonQCAdapter
from src.adapters.dummy_adapter import DummyToolAdapter
from src.adapters.esmfold_adapter import ESMFoldAdapter
from src.adapters.nim_adapter import NIMESMFoldAdapter
from src.adapters.openfold_adapter import OpenFold3Adapter
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
    openfold3_rest_available = bool(os.getenv("OPENFOLD3_REST_BASE_URL"))
    if not openfold3_rest_available:
        try:
            provider_cfg = get_provider_config("openfold3_rest")
            openfold3_rest_available = bool(provider_cfg.base_url)
        except KeyError:
            openfold3_rest_available = False
    if nim_api_key or openfold3_rest_available:
        try:
            get_adapter(OpenFold3Adapter.tool_id)
        except KeyError:
            register_adapter(OpenFold3Adapter())
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
