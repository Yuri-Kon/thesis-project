"""PlannerAgent 的 LLM Provider 抽象层

本模块提供可插拔的 LLM providers 用于生成计划。

可用的 providers:
- BaselineProvider: 简单确定性 provider
- OpenAICompatibleProvider: OpenAI 兼容 API provider (需要 'openai' 包)

示例:
    from src.llm import BaselineProvider, ProviderConfig
    from src.agents.planner import PlannerAgent

    config = ProviderConfig(model_name="baseline")
    provider = BaselineProvider(config)
    planner = PlannerAgent(llm_provider=provider)
"""

from src.llm.base_llm_provider import BaseProvider, ProviderConfig
from src.llm.baseline_provider import BaselineProvider

# OpenAICompatibleProvider 需要可选的 'openai' 包
try:
    from src.llm.openai_compatible_provider import OpenAICompatibleProvider
    __all__ = [
        "BaseProvider",
        "ProviderConfig",
        "BaselineProvider",
        "OpenAICompatibleProvider"
    ]
except ImportError:
    __all__ = ["BaseProvider", "ProviderConfig", "BaselineProvider"]
