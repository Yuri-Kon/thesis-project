"""OpenAI 兼容的 LLM Provider

支持任何使用 OpenAI 兼容 API 的 LLM 服务，包括:
- OpenAI (GPT-4, GPT-3.5, 等)
- Nemotron (NVIDIA)
- Anthropic (使用兼容层时)
- 本地模型 via vLLM, LocalAI, 等
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Dict, List, Optional

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from src.llm.base_llm_provider import BaseProvider, ProviderConfig
from src.models.contracts import ProteinDesignTask

if TYPE_CHECKING:
    from src.agents.planner import ToolSpec


class OpenAICompatibleProvider(BaseProvider):
    """使用 OpenAI 兼容 API 的 LLM provider

    通过提示 LLM 任务详情和工具注册表来生成计划。
    LLM 需要返回 JSON 格式的 Plan。
    """

    def __init__(self, config: ProviderConfig, endpoint: Optional[str] = None):
        """初始化 OpenAI 兼容 provider

        Args:
            config: Provider 配置 (model_name, api_key, timeout, max_tokens)
            endpoint: 可选的自定义 API endpoint (用于 Nemotron, vLLM, 等)
                     如果为 None，使用默认 OpenAI endpoint

        Raises:
            ImportError: 如果未安装 openai 包
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "OpenAICompatibleProvider 需要 openai 包。安装方式: pip install openai"
            )

        self.config = config
        self.endpoint = endpoint

        # 初始化 OpenAI 客户端
        client_kwargs = {"api_key": config.api_key or "dummy-key"}
        if endpoint:
            client_kwargs["base_url"] = endpoint

        self.client = OpenAI(**client_kwargs)

    def call_planner(
        self, task: ProteinDesignTask, tool_registry: List["ToolSpec"]
    ) -> Dict:
        """使用 LLM 生成计划

        Args:
            task: 蛋白质设计任务
            tool_registry: 可用工具

        Returns:
            Plan 的 Dict 表示

        Raises:
            ValueError: 如果 LLM 返回无效 JSON 或计划格式
            Exception: 如果 API 调用失败
        """
        # 构建系统提示词
        system_prompt = self._build_system_prompt()

        # 构建包含任务和工具的用户提示词
        user_prompt = self._build_user_prompt(task, tool_registry)

        # 调用 LLM
        start_time = time.time()
        try:
            request_kwargs = {
                "model": self.config.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": self.config.max_tokens,
                "timeout": self.config.timeout,
                "temperature": self.config.temperature,
                "top_p": self.config.top_p,
            }
            if self.config.extra_body:
                request_kwargs["extra_body"] = self.config.extra_body
            if self.config.stream:
                request_kwargs["stream"] = True
            elif self.config.use_response_format:
                request_kwargs["response_format"] = {"type": "json_object"}

            response = self.client.chat.completions.create(**request_kwargs)
        except Exception as e:
            raise Exception(f"LLM API 调用失败: {e}")

        elapsed = time.time() - start_time

        # 提取响应内容
        if self.config.stream:
            content = self._collect_stream_content(response)
        else:
            content = response.choices[0].message.content
        if not content:
            raise ValueError("LLM 返回空响应")

        # 解析 JSON
        try:
            plan_dict = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM 返回无效 JSON: {e}\n内容: {content}")

        # 验证基本结构
        if not isinstance(plan_dict, dict):
            raise ValueError(f"LLM 响应不是 dict: {type(plan_dict)}")

        # 确保必需字段存在
        if "steps" not in plan_dict:
            raise ValueError("LLM 响应缺少 'steps' 字段")

        # 如果缺少 task_id 则添加
        if "task_id" not in plan_dict:
            plan_dict["task_id"] = task.task_id

        # 添加元数据
        if "metadata" not in plan_dict:
            plan_dict["metadata"] = {}
        plan_dict["metadata"].update(
            {
                "provider": "openai_compatible",
                "model": self.config.model_name,
                "elapsed_seconds": elapsed,
                "endpoint": self.endpoint or "default",
            }
        )

        # 根据 Plan schema 验证
        if not self.validate_plan(plan_dict):
            raise ValueError(f"LLM 生成的 Plan 无效: {plan_dict}")

        return plan_dict

    def _build_system_prompt(self) -> str:
        """构建 LLM 的系统提示词"""
        return """你是一个蛋白质设计规划助手。你的任务是为蛋白质设计任务生成多步执行计划。

给定:
- 一个带有目标和约束的蛋白质设计任务
- 一个包含工具能力的可用工具注册表

输出:
- 一个遵循此 schema 的有效 JSON 计划:
  {
    "task_id": "string (将被提供)",
    "steps": [
      {
        "id": "S1", "S2", 等 (顺序步骤 ID),
        "tool": "来自注册表的 tool_id",
        "inputs": {
          "param": "值或符号引用如 'S1.sequence'"
        },
        "metadata": {}
      }
    ],
    "constraints": {},
    "metadata": {"explanation": "此计划的简要推理"}
  }

规则:
1. 步骤 ID 必须顺序: S1, S2, S3, 等
2. 工具名称必须与注册表中的 tool ID 完全匹配
3. 使用符号引用 (如 "S1.sequence") 来引用前序步骤的输出
4. 不要内联或计算实际值 - 保持引用的符号形式
5. 链接步骤时考虑工具能力、输入和输出
6. 尽可能选择更简单的计划
7. 始终返回有效的 JSON
"""

    def _build_user_prompt(
        self, task: ProteinDesignTask, tool_registry: List["ToolSpec"]
    ) -> str:
        """构建包含任务和工具信息的用户提示词"""
        # 格式化工具注册表
        tools_desc = []
        for tool in tool_registry:
            tools_desc.append(
                f"- {tool.id}:\n"
                f"  能力: {', '.join(tool.capabilities)}\n"
                f"  输入: {', '.join(tool.inputs)}\n"
                f"  输出: {', '.join(tool.outputs)}\n"
                f"  成本: {tool.cost}, 安全级别: {tool.safety_level}"
            )

        tools_text = "\n".join(tools_desc)

        return f"""任务 ID: {task.task_id}
目标: {task.goal}
约束: {json.dumps(task.constraints, indent=2)}

可用工具:
{tools_text}

请生成一个多步计划来完成这个蛋白质设计任务。仅返回遵循系统提示中 schema 的有效 JSON。
"""

    def _collect_stream_content(self, stream) -> str:
        """从流式响应中拼接内容"""
        chunks: List[str] = []
        for chunk in stream:
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                chunks.append(content)
        return "".join(chunks)
