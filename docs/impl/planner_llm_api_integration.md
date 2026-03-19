# Planner 外部 LLM 接入规范
<!-- SID:impl.planner_llm.overview -->

本文件给后续实现 Planner LLM 接入的 Codex/LLM 直接提供工程化指导。

适用范围：

- 仅覆盖 Planner 侧的外部 LLM 调用，不改变 FSM、HITL 契约、Agent 边界。
- 目标是让 `src/llm/` 能按 provider 切换不同外部模型，并保持同一 `Plan/PlanPatch/Replan` 输出契约。
- 本文优先映射当前实现：`src/llm/base_llm_provider.py`、`src/llm/openai_compatible_provider.py`、`src/llm/provider_registry.py`、`configs/llm_providers.json`。

必须同时遵守：

- [ref:SID:planner.responsibilities.must]
- [ref:SID:planner.responsibilities.must_not]
- [ref:SID:impl.planner.tool_resolution]
- [ref:SID:impl.remote_model_invocation.provider_config]

## 总体接入原则

1. Provider 只负责生成候选 `Plan` / `PlanPatch` / `Replan`，不执行工具，不修改任务状态。
2. 工具清单必须来自 ProteinToolKG；外部模型只能在给定注册表内选择工具，或输出 `"unknown" + metadata.capability"` 交由本地 ToolResolver 收敛。
3. 所有模型输出都必须经过本地 JSON 解析、Pydantic 校验、工具合法性校验、符号引用校验。
4. 结构化输出优先级：
   - 第一优先：严格 schema/function calling
   - 第二优先：JSON schema / JSON object
   - 第三优先：文本 JSON + 本地重试修复
5. Planner 是高约束场景，默认应优先低温、低随机性、强结构约束，而不是追求发散创意。

### Provider 选型与适配层建议
<!-- SID:impl.planner_llm.provider_selection -->

推荐按 API 协议分三类接入，而不是为每个厂商写完全独立的 Planner 逻辑：

| 厂商/模型 | 建议 provider_type | 推荐基础 URL | 当前代码可复用程度 | 结构化输出建议 |
| --- | --- | --- | --- | --- |
| OpenAI GPT-5.4 | `openai_responses` 或短期 `openai_compatible` | OpenAI 默认 API | 中 | 原生 JSON Schema / strict function calling |
| Anthropic Claude | `anthropic_messages` | `https://api.anthropic.com/v1` | 低 | 用 tool use 输出结构化对象 |
| DeepSeek | `openai_compatible` | `https://api.deepseek.com/v1` | 高 | `response_format=json_object` 或 strict tools(beta) |
| Qwen (DashScope/百炼) | `openai_compatible` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 高 | 优先 `json_schema`；工具调用可用 |
| GLM (智谱) | `anthropic_messages` 优先；次选 OpenAI 兼容层若后续验证可行 | `https://open.bigmodel.cn/api/anthropic` | 中 | 优先 tool use；JSON Object 可作为兜底 |
| NVIDIA NIM Nemotron | `openai_compatible` | 视部署而定，云侧常见为 `https://integrate.api.nvidia.com/v1` 或 NIM `/v1` | 高 | 以 function calling / JSON 输出为主，能力取决于具体 Nemotron 版本 |

工程建议：

- 不要把“Claude Code”当作模型名或 provider 名。它是 Anthropic 的产品形态，不是 Planner 侧直接调用的 API 模型。接入时应落到 Claude Messages API 或兼容层。
- 不要把“ChatGPT 5.4”写成 provider 名。API 里应使用 OpenAI 模型标识 `gpt-5.4` 或 `gpt-5.4-pro`。OpenAI 已在 2026-03 发布说明中确认这两个 API 模型可直接调用。
- Qwen、DeepSeek、Nemotron 均可优先走当前的 `OpenAICompatibleProvider` 演进线。
- Claude/GLM 的最佳接入点是新增 `AnthropicMessagesProvider`，不要强行塞进 OpenAI `chat.completions` 语义。

### Planner 参数基线
<!-- SID:impl.planner_llm.parameter_baseline -->

对 Planner 任务，推荐默认参数如下：

| 参数 | 推荐值 | 说明 |
| --- | --- | --- |
| `temperature` | `0.0 - 0.3` | 优先确定性与 schema 合法率 |
| `top_p` | `1.0` | 一般保持默认，避免同时调高随机性 |
| `max_tokens` / `max_output_tokens` | `3000 - 8000` | 视 `Plan/Patch/Replan` 复杂度调整 |
| `stream` | `false` | Planner 首选非流式，便于一次性解析结构化输出 |
| `use_response_format` | `true`（若 provider 支持） | 优先开启结构化输出 |
| `tool_choice` | 结构化发射工具时设为 `required` / `any` / 指定工具 | 避免模型输出散文解释 |

针对思考/推理模型：

- Planner 默认不要开启“深度思考 + 流式”作为首选路径，因为这会显著增加解析复杂度与时延。
- 若某模型的结构化输出与 thinking 模式冲突，应优先关闭 thinking，保留强结构输出。
- 仅在本地 schema 合法率下降、复杂任务质量明显不足时，再用 reasoning 版本做 fallback。

### 结构化输出契约
<!-- SID:impl.planner_llm.structured_output_contract -->

无论底层厂商如何，Provider 最终都应向 `BaseProvider` 返回同一类 Python `dict`：

- 初始规划：`Plan`
- 失败修复：`PlanPatch`
- 后缀重规划：`Plan`

推荐使用“发射器工具”统一结构化输出：

```json
{
  "type": "function",
  "function": {
    "name": "emit_plan",
    "description": "Emit one valid planner candidate",
    "strict": true,
    "parameters": {
      "type": "object",
      "properties": {
        "task_id": {"type": "string"},
        "steps": {"type": "array"},
        "constraints": {"type": "object"},
        "metadata": {"type": "object"}
      },
      "required": ["task_id", "steps", "constraints", "metadata"],
      "additionalProperties": false
    }
  }
}
```

对 Claude / GLM 这类没有 OpenAI `response_format` 语义的接口，优先让模型调用 `emit_plan` 或 `emit_patch` 工具，再从工具参数中读取结构化对象。

### Provider 配置契约
<!-- SID:impl.planner_llm.config_contract -->

`configs/llm_providers.json` 建议继续作为 Planner LLM 的唯一 provider 目录；字段与现有 `ProviderSettings` / `ProviderConfig` 保持兼容，并做最小增量扩展。

当前已存在的通用字段：

- `provider_type`
- `description`
- `model_name`
- `api_key_env`
- `endpoint`
- `timeout`
- `max_tokens`
- `temperature`
- `top_p`
- `stream`
- `extra_body`
- `use_response_format`

建议为后续扩展追加的可选字段：

- `api_style`: `openai_chat` | `openai_responses` | `anthropic_messages`
- `structured_output_mode`: `json_schema` | `json_object` | `tool_call` | `text_json`
- `tool_strategy`: `none` | `auto` | `required` | `emit_plan`
- `supports_patch`
- `supports_replan`
- `supports_reasoning`
- `headers`
- `organization`
- `anthropic_version`

推荐配置样例：

```json
{
  "providers": {
    "openai_gpt54": {
      "provider_type": "openai_compatible",
      "api_style": "openai_responses",
      "description": "OpenAI GPT-5.4 for planner",
      "model_name": "gpt-5.4",
      "api_key_env": "OPENAI_API_KEY",
      "timeout": 60,
      "max_tokens": 4000,
      "temperature": 0.2,
      "top_p": 1.0,
      "stream": false,
      "use_response_format": true,
      "structured_output_mode": "json_schema"
    },
    "anthropic_claude_sonnet4": {
      "provider_type": "anthropic_messages",
      "api_style": "anthropic_messages",
      "description": "Claude Sonnet 4 for planner",
      "model_name": "claude-sonnet-4",
      "api_key_env": "ANTHROPIC_API_KEY",
      "endpoint": "https://api.anthropic.com/v1",
      "timeout": 60,
      "max_tokens": 4000,
      "temperature": 0.2,
      "tool_strategy": "emit_plan",
      "structured_output_mode": "tool_call",
      "anthropic_version": "2023-06-01"
    }
  }
}
```

### OpenAI GPT-5.4 接入
<!-- SID:impl.planner_llm.openai -->

截至 2026-03，OpenAI 已确认 `gpt-5.4` 与 `gpt-5.4-pro` 可通过 API 直接调用。

推荐接入方式：

- 中短期：继续复用当前 `OpenAICompatibleProvider`，通过 Chat Completions 路径接入。
- 中长期：新增 `OpenAIResponsesProvider`，使用 Responses API 的 `text.format = json_schema` 或 strict function calling。

建议配置：

- `model_name`: `gpt-5.4`
- `api_key_env`: `OPENAI_API_KEY`
- `temperature`: `0.1 - 0.2`
- `top_p`: `1.0`
- `stream`: `false`
- `structured_output_mode`: `json_schema`

能力判断：

- 强项：严格结构化输出、复杂规划、长上下文、多工具规划。
- 结构化输出：强。OpenAI 官方建议优先使用 Structured Outputs，而不是旧的 JSON mode。
- 适合本项目的模式：`emit_plan` function calling 或 Responses API `json_schema`。

落地建议：

1. 若沿用当前 `OpenAICompatibleProvider`，至少把 `response_format={"type":"json_object"}` 升级为可配置。
2. 新增 OpenAI 专用 provider 时，优先把 `Plan` schema 转换为受支持的 JSON Schema 子集，并强制 `additionalProperties: false`。
3. 对 `PlanPatch` 和 `Replan` 也复用相同结构化路径，不要退回纯文本。

### Anthropic Claude 接入
<!-- SID:impl.planner_llm.anthropic -->

Claude 最适合通过 Messages API 接入，而不是伪装成 OpenAI Chat Completions。

推荐配置：

- `provider_type`: `anthropic_messages`
- `endpoint`: `https://api.anthropic.com/v1`
- `api_key_env`: `ANTHROPIC_API_KEY`
- `model_name`: 建议从 `claude-sonnet-4` 起步，复杂场景可切 `claude-opus-4`
- `max_tokens`: `4096`
- `temperature`: `0.2`

重要差异：

- 参数语义与 OpenAI 不同，关键入口是 `messages.create(...)`。
- 结构化输出不应依赖 OpenAI 风格 `response_format`。
- 官方推荐的强结构路径是 tool use：在 `tools` 中声明 JSON Schema `input_schema`，模型返回 `tool_use` 块，`input` 即结构化对象。
- 当启用 extended thinking 时，某些强制 `tool_choice` 方式不可用；Planner 场景下应优先关闭 thinking，保证结构化稳定性。

本项目接入建议：

1. 新增 `AnthropicMessagesProvider`。
2. 为 `Plan`、`PlanPatch`、`Replan` 定义三个发射器工具：`emit_plan`、`emit_patch`、`emit_replan`。
3. Provider 只接受 tool call 结果；若 Claude 只返回文本，则视为不合格响应并触发重试。

### DeepSeek 接入
<!-- SID:impl.planner_llm.deepseek -->

DeepSeek 目前最容易接入当前代码。官方提供 OpenAI 兼容的 `/chat/completions`，模型至少包括 `deepseek-chat` 和 `deepseek-reasoner`。

推荐配置：

- `provider_type`: `openai_compatible`
- `endpoint`: `https://api.deepseek.com/v1`
- `api_key_env`: `DEEPSEEK_API_KEY`
- `model_name`: 初始建议 `deepseek-chat`
- `temperature`: `0.2`
- `use_response_format`: `true`
- `stream`: `false`

能力判断：

- JSON Output：支持，`response_format={"type":"json_object"}` 可保证返回合法 JSON。
- Tool Calls：支持。
- Strict tools：支持 beta strict mode，但需要切到 `https://api.deepseek.com/beta`，并在每个 `function` 上设置 `strict: true`。

本项目建议：

- 初始集成优先 `deepseek-chat + json_object + 本地 schema 校验`。
- 若需要更高结构稳定性，可新增 `deepseek_strict_tools` 配置，切到 beta base URL 并用 `emit_plan` 工具。
- `deepseek-reasoner` 可作为 fallback，不建议直接作为默认 Planner。

### Qwen / DashScope 接入
<!-- SID:impl.planner_llm.qwen -->

Qwen（阿里云百炼 / DashScope）对本项目很友好，因为既支持 OpenAI 兼容 Chat Completions，也已经提供兼容 Responses API。

推荐配置：

- `provider_type`: `openai_compatible`
- `endpoint`: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- `api_key_env`: `DASHSCOPE_API_KEY`
- `model_name`: 初始建议 `qwen-plus` 或更高档位模型
- `temperature`: `0.2`
- `stream`: `false`

关键能力：

- JSON Object：支持，但 prompt 中必须出现 `JSON` 关键词。
- JSON Schema：支持，且更适合生产。Qwen 官方明确建议自动化场景优先 `json_schema`。
- Function Calling：支持 `tools`、`tool_choice`、`parallel_tool_calls`。
- Responses API：已提供 OpenAI 兼容接口，可作为后续升级路线。

注意事项：

- 开启结构化输出时，不要显式限制 `max_tokens`，否则可能截断 JSON。
- 开启 thinking 模式时，不要再设置 `response_format={"type":"json_object"}`；官方文档说明这会报错。
- 若使用思考模型，通常要改为流式输出；这不适合当前 Planner 的首选路径。

本项目建议：

1. 非思考模式下，优先 `json_schema`。
2. 需要工具规划时，可直接用 `emit_plan` function calling。
3. 对于生产稳定性，Qwen 是本项目最适合首批接入的国内 provider 之一。

### GLM / 智谱 接入
<!-- SID:impl.planner_llm.glm -->

GLM 的工程接入建议分两层理解：

- 若追求最快落地，可利用智谱提供的 Claude API 兼容层。
- 若追求长期稳定，应把它视为“Anthropic 协议 provider”，而不是 OpenAI provider。

已确认的兼容入口：

- `base_url`: `https://open.bigmodel.cn/api/anthropic`
- SDK：可直接复用 Anthropic SDK
- 文档中给出的示例模型包括 `glm-5`、`glm-4.7`

能力判断：

- 工具调用：支持，智谱官方文档已给出 `tools` / `tool_calls` 语义。
- 结构化输出：可走 tool calling；若只是简单结构，可走 JSON Object 风格输出。
- 对“Claude Code 迁移”友好，但那属于产品迁移语义，不等于本项目应直接接入“Claude Code”。

本项目建议：

1. 直接复用后续的 `AnthropicMessagesProvider`，只替换 `base_url` 和模型名。
2. 统一使用 `emit_plan` 工具，不要依赖自由文本 JSON。
3. 把 GLM 归类为 `anthropic_messages` 风格 provider，可减少专用代码。

### NVIDIA NIM Nemotron 接入
<!-- SID:impl.planner_llm.nemotron -->

Nemotron 适合作为高性能外部 fallback，尤其适合长上下文和 agentic workflow。

推荐配置：

- `provider_type`: `openai_compatible`
- `endpoint`: 依据部署方式填写；云托管常见 OpenAI 兼容 `/v1`
- `api_key_env`: `NIM_API_KEY`
- `model_name`: 按具体部署模型填写，例如 `nvidia/nemotron-3-nano-30b-a3b` 或更新版本

官方资料显示：

- Nemotron 模型普遍强调 tool use / agentic workflow。
- 某些新版本支持通过 `enable_thinking=True/False` 控制 reasoning。
- 文档给出推荐参数时，tool calling 常见推荐值比 reasoning 模式更保守。

本项目建议：

- 默认关闭 thinking，优先输出稳定结构。
- 在 `extra_body` 中放 NIM 特有参数，例如 `chat_template_kwargs.enable_thinking`。
- 若特定 Nemotron 版本对 function calling 表现稳定，优先用 `emit_plan`；否则退回 JSON object + 本地校验。
- 当前仓库里 `configs/llm_providers.json` 的 `nemotron` 项可保留，但推荐把默认 `temperature` 从 `1.0` 下调到 Planner 友好的低温值，除非明确作为 reasoning fallback。

### 输出校验、重试与回退
<!-- SID:impl.planner_llm.validation_and_fallback -->

无论 provider 如何，统一执行以下本地门禁：

1. 响应必须可提取为单个结构化对象。
2. 必须通过 `Plan` / `PlanPatch` Pydantic 校验。
3. 所有 `tool` 必须存在于 KG，或满足 `"unknown" + capability` 的降级约定。
4. 所有步骤 ID 必须是顺序 `S1...Sn`。
5. 所有前序引用必须保持符号形式，如 `S1.sequence`。

推荐回退顺序：

1. 同 provider 低成本重试一次
2. 同 provider 切换到更强结构模式
3. 切换到更强模型
4. 切换到外部兜底 provider
5. 仍失败则回到 baseline provider 或进入 HITL

不要做的事：

- 不要在 provider 中直接补执行结果。
- 不要让模型自由发明 KG 外工具。
- 不要把“reasoning 文本很像对的”当成结构合法。

## 推荐的首批接入优先级

1. Qwen：最容易落地到当前 `OpenAICompatibleProvider`，结构化输出能力强。
2. OpenAI GPT-5.4：适合作为高质量主力或高级 fallback。
3. DeepSeek：接入成本低，适合成本敏感路径。
4. Claude：质量高，但需要新增 Anthropic provider。
5. GLM：复用 Anthropic provider 后接入成本可控。
6. Nemotron：适合作为长上下文/高性能 fallback，而不是首个默认 provider。

## 参考资料

- OpenAI GPT-5.4 发布页：https://openai.com/zh-Hans-CN/index/introducing-gpt-5-4/
- OpenAI Structured Outputs：https://platform.openai.com/docs/guides/structured-outputs
- Anthropic Tool Use：https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/implement-tool-use
- Anthropic JSON consistency guidance：https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency
- DeepSeek Chat Completion API：https://api-docs.deepseek.com/api/create-chat-completion/
- DeepSeek Function Calling：https://api-docs.deepseek.com/guides/function_calling/
- DeepSeek Models & Pricing：https://api-docs.deepseek.com/quick_start/pricing
- Qwen 结构化输出：https://help.aliyun.com/zh/model-studio/qwen-structured-output
- Qwen Function Calling：https://help.aliyun.com/zh/model-studio/qwen-function-calling
- Qwen Responses API 兼容：https://help.aliyun.com/zh/model-studio/qwen-api-via-openai-responses
- 智谱 Claude API 兼容：https://docs.bigmodel.cn/cn/guide/develop/claude/introduction
- 智谱工具调用：https://docs.bigmodel.cn/cn/guide/capabilities/function-calling
- NVIDIA Nemotron 模型参考：https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-nano-30b-a3b
