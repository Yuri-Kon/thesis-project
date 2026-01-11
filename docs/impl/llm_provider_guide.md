# LLM Provider 集成指南
<!-- SID:impl.llm_provider.guide -->

本指南说明如何在 PlannerAgent 中使用可插拔的 LLM providers。

## 概述

Issue #75 引入了可插拔的 LLM provider 架构，允许在不同的 LLM 后端之间切换以生成计划，同时保持向后兼容性。

## 架构

```
┌─────────────────┐
│ PlannerAgent    │
└────────┬────────┘
         │ 使用 (可选)
         ▼
┌─────────────────┐
│  BaseProvider   │ (抽象)
└────────┬────────┘
         │ 实现
         ├──► BaselineProvider (确定性)
         ├──► OpenAICompatibleProvider (GPT-4, Nemotron, 等)
         └──► [您的自定义 provider]
```

## 可用的 Providers

### 1. BaselineProvider (默认)

生成单步计划的简单确定性 provider。

**特性:**
- 无 LLM 调用
- 快速且可预测
- 适合测试和基线对比

**用法:**
```python
from src.agents.planner import PlannerAgent
from src.llm.baseline_provider import BaselineProvider
from src.llm.base_llm_provider import ProviderConfig

config = ProviderConfig(model_name="baseline")
provider = BaselineProvider(config)
planner = PlannerAgent(llm_provider=provider)
```

### 2. OpenAICompatibleProvider
<!-- SID:impl.llm_provider.external_providers -->

支持任何 OpenAI 兼容的 API endpoint。

**支持的服务:**
- OpenAI (GPT-4, GPT-3.5, 等)
- NVIDIA Nemotron
- Anthropic Claude (通过兼容层)
- 本地模型 (vLLM, LocalAI, 等)

**使用 OpenAI:**
```python
import os
from src.llm.openai_compatible_provider import OpenAICompatibleProvider
from src.llm.base_llm_provider import ProviderConfig

config = ProviderConfig(
    model_name="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=30,
    max_tokens=2000
)

provider = OpenAICompatibleProvider(config)
planner = PlannerAgent(llm_provider=provider)
```

**使用 NVIDIA Nemotron:**
```python
import os
from src.llm.openai_compatible_provider import OpenAICompatibleProvider
from src.llm.base_llm_provider import ProviderConfig

config = ProviderConfig(
    model_name="nvidia/llama-3.1-nemotron-70b-instruct",
    api_key=os.getenv("NVIDIA_API_KEY"),
    timeout=30,
    max_tokens=2000
)

endpoint = "https://integrate.api.nvidia.com/v1"
provider = OpenAICompatibleProvider(config, endpoint=endpoint)
planner = PlannerAgent(llm_provider=provider)
```

## 向后兼容性

PlannerAgent 在没有 provider 的情况下仍可工作（保持原有行为）：

```python
planner = PlannerAgent()  # 无 provider = 使用默认单步计划
plan = planner.plan(task)  # 像之前一样工作
```

## 对比脚本

使用提供的脚本来对比不同的 providers：

```bash
# 仅对比 baseline provider
python scripts/compare_providers.py --providers baseline

# 对比多个 providers
python scripts/compare_providers.py --providers baseline,openai,nemotron \
    --output logs/my_comparison

# 使用自定义 API 密钥
python scripts/compare_providers.py --providers openai \
    --api-key your-api-key-here
```

**输出:**
- `comparison_YYYYMMDD_HHMMSS.jsonl`: 包含详细结果的 JSON Lines 格式
- `summary_YYYYMMDD_HHMMSS.json`: 包含所有指标的完整摘要

**示例输出:**
```
================================================================================
摘要
================================================================================
Provider        任务                   步骤数    耗时 (s)   状态
--------------------------------------------------------------------------------
baseline        benchmark_simple     1        0.001      ✓
baseline        benchmark_complex    1        0.001      ✓
baseline        benchmark_multistep  1        0.001      ✓
openai          benchmark_simple     3        1.245      ✓
openai          benchmark_complex    4        2.156      ✓
openai          benchmark_multistep  5        1.892      ✓
================================================================================
```

## 环境变量

为方便起见，设置这些环境变量：

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# NVIDIA Nemotron
export NVIDIA_API_KEY="nvapi-..."
export NVIDIA_API_ENDPOINT="https://integrate.api.nvidia.com/v1"
```

## 创建自定义 Providers

实现 `BaseProvider` 接口：

```python
from src.llm.base_llm_provider import BaseProvider, ProviderConfig
from src.models.contracts import ProteinDesignTask
from typing import Dict, List

class MyCustomProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        self.config = config
        # 在此初始化您的 LLM 客户端

    def call_planner(
        self,
        task: ProteinDesignTask,
        tool_registry: List["ToolSpec"]
    ) -> Dict:
        """使用您的 LLM 生成计划

        Returns:
            包含 Plan schema 的 Dict:
            {
                "task_id": str,
                "steps": [
                    {
                        "id": "S1",
                        "tool": "tool_id",
                        "inputs": {...},
                        "metadata": {}
                    }
                ],
                "constraints": {...},
                "metadata": {}
            }
        """
        # 您的实现在此
        plan_dict = self._call_my_llm(task, tool_registry)

        # 返回前验证
        if not self.validate_plan(plan_dict):
            raise ValueError("生成的计划无效")

        return plan_dict
```

## 测试

运行测试以验证 provider 集成：

```bash
# 测试现有 PlannerAgent（向后兼容性）
pytest tests/unit/test_planner_agent.py -v

# 测试 provider 集成
pytest tests/unit/test_planner_with_provider.py -v

# 运行所有测试
pytest tests/unit/ -v
```

## 关键约束

实现 providers 时，确保：

1. **步骤引用保持符号形式**: 使用 `"S1.sequence"` 格式，不要内联值
2. **有效的 Plan schema**: 输出必须能通过 `Plan` 模型验证
3. **工具 ID 必须存在**: 引用的工具必须在工具注册表中
4. **不执行工具**: Providers 仅生成计划，不执行工具
5. **向后兼容性**: 没有 providers 的现有代码必须仍然可以工作

## 故障排除

### 循环导入错误
如果看到 `ImportError: cannot import name 'ToolSpec'`，provider 模块可能有错误的导入。使用：
```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.agents.planner import ToolSpec
```

### API 密钥问题
- 检查环境变量是否正确设置
- 验证 API 密钥格式是否符合 provider 的要求
- 使用 `python -c "import os; print(os.getenv('OPENAI_API_KEY'))"` 测试

### 无效计划错误
- 使用 `provider.validate_plan(plan_dict)` 检查计划格式
- 确保所有必需字段都存在: `task_id`, `steps`, `constraints`, `metadata`
- 检查步骤结构: 每个步骤需要 `id`, `tool`, `inputs`, `metadata`

## 设计原则

本实现遵循 AGENT_CONTRACT.md：

- ✅ PlannerAgent 仅生成计划（不执行）
- ✅ FSM 状态转换保持不变
- ✅ Plan schema 向后兼容
- ✅ Agent 边界受到尊重
- ✅ 对现有代码的最小改动

## 参考资料

- Issue #75: 添加带 Nemotron baseline 的可插拔 LLM provider
- `AGENT_CONTRACT.md`: 系统级行为契约
- `src/agents/planner.py`: PlannerAgent 实现
- `src/llm/`: Provider 实现
