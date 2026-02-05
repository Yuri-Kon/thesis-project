# 章节可寻址契约 (Section Identifier Contract)

## 1. 概述

本文档定义了一套统一的"章节可寻址契约"（Section Identifier Contract），用于在本项目的 Markdown 设计文档中稳定、精确地定位规范片段。该契约是后续脚本（如 `docslice`）、linting 工具以及 Claude Code Skills 的法规来源。

**核心目标**：

- 提供稳定、唯一的章节标识符（Section Identifier, SID）
- 支持跨文档引用与自动化文档切片提取
- 为 Claude Code Skills 提供可解析的规范定位机制
- 确保设计文档的可维护性与可追溯性

## 2. SID 定义

### 2.1 命名格式

所有章节标识符必须遵循以下格式：

```
SID:<domain>.<topic>.<name>
```

**格式说明**：

- `<domain>`：领域标识符，见 2.2 节
- `<topic>`：主题标识符，表示该领域下的具体主题或子系统
- `<name>`：具体名称，标识该主题下的特定章节、规范或项

**示例**：

```
SID:fsm.states.planning
SID:planner.algorithm.candidate_scoring
SID:tools.esmfold.input_schema
SID:hitl.decision.approval_flow
```

### 2.2 Domain 推荐集合

为保持一致性，推荐使用以下 domain 标识符：

| Domain | 说明 | 适用文档 |
|--------|------|----------|
| `fsm` | 有限状态机相关规范 | architecture.md, system-implementation-design.md |
| `hitl` | Human-in-the-loop 机制 | hitl-extension.md, agent-design.md |
| `planner` | Planner Agent 相关 | agent-design.md, core-algorithm-spec.md |
| `executor` | Executor Agent 相关 | agent-design.md, system-implementation-design.md |
| `tools` | 工具集成与适配器 | tools-catalog.md, system-implementation-design.md |
| `obs` | 可观测性、日志与监控 | system-implementation-design.md |
| `storage` | 数据存储与持久化 | system-implementation-design.md |
| `safety` | Safety Agent 与安全机制 | agent-design.md, system-implementation-design.md |
| `summarizer` | Summarizer Agent 与报告生成 | agent-design.md, system-implementation-design.md |
| `arch` | 总体架构与分层设计 | architecture.md |
| `workflow` | de novo 工作流分层与模块化设计 | de-novo-workflow.md |
| `api` | REST API 与接口契约 | system-implementation-design.md |
| `kg` | ProteinToolKG 知识图谱 | system-implementation-design.md |

**扩展性**：

- 当上述 domain 无法满足需求时，可引入新 domain，但必须在本文档中进行注册
- 新 domain 应具有明确的语义边界，避免与现有 domain 重叠

### 2.3 Topic 与 Name 命名规范

- **Topic**：使用小写英文单词或缩写，多个单词用下划线分隔（`snake_case`）
- **Name**：使用小写英文单词或缩写，多个单词用下划线分隔（`snake_case`）
- **长度限制**：`topic` 和 `name` 各不超过 32 个字符
- **字符集**：仅允许 `a-z`、`0-9`、`_`（下划线）

**反例**：

```
❌ SID:FSM.States.Planning  (使用了大写)
❌ SID:planner.algorithm.Candidate-Scoring  (使用了短横线和大写)
❌ SID:tools.ESMFold.inputSchema  (使用了驼峰命名)
```

**正例**：

```
✓ SID:fsm.states.planning
✓ SID:planner.algorithm.candidate_scoring
✓ SID:tools.esmfold.input_schema
```

## 3. 粒度定义

本契约定义三种粒度层级，用于不同规模的文档片段寻址：

### 3.1 Section（章节级）

**定义**：对应 Markdown 的一级或二级标题（`#` 或 `##`），代表一个完整的主题或模块。

**用途**：

- 标识文档的主要组成部分
- 作为跨文档引用的主要锚点
- 用于生成文档索引与导航

**标注位置**：紧邻标题之后或之前

**示例**：

```markdown
## 任务生命周期与状态机
<!-- SID:fsm.lifecycle.overview -->

任务从创建到完成经历以下状态...
```

### 3.2 Block（块级）

**定义**：对应 Markdown 的三级或四级标题（`###` 或 `####`），或一段逻辑完整的内容块（表格、代码块、列表等）。

**用途**：

- 标识章节内的子主题或具体规范点
- 用于精确定位算法描述、数据结构定义等
- 支持细粒度的文档切片提取

**标注位置**：紧邻块内容之前或之后

**示例**：

```markdown
### FSM 状态定义
<!-- SID:fsm.states.definitions -->

| 状态 | 说明 | 允许的转换 |
|------|------|-----------|
| CREATED | 任务已创建 | PLANNING |
| PLANNING | 规划中 | PLANNED, FAILED |
```

### 3.3 Spec-Item（规范项级）

**定义**：最细粒度的可寻址单元，对应单个规范条目、约束条件、API 定义等。

**用途**：

- 标识可被脚本直接提取的规范片段
- 用于 linting 规则与合规性检查
- 支持 Claude Code Skills 的精确规范检索

**标注位置**：使用 `BEGIN/END` 边界标记

**示例**：

```markdown
<!-- SID:planner.constraints.timeout BEGIN -->
**规范**: Planner Agent 必须在 30 秒内返回初始计划，否则触发超时错误。
<!-- SID:planner.constraints.timeout END -->
```

### 3.4 粒度选择建议

| 粒度 | 适用场景 | 估计长度 |
|------|----------|----------|
| Section | 文档主要组成部分、大模块 | 数十行至数百行 |
| Block | 子主题、数据结构、算法步骤 | 数行至数十行 |
| Spec-Item | 单个约束、规则、API 定义 | 1-5 行 |

**原则**：

- 优先使用 Section 和 Block 级别，除非有明确需求定位到具体规范项
- Spec-Item 应保持原子性，即该规范项不可再拆分为更小的独立规范

## 4. Markdown 标注方式

### 4.1 基本语法

使用 HTML 注释标记 SID，格式如下：

```markdown
<!-- SID:<domain>.<topic>.<name> -->
```

**位置规则**：

- **Section 和 Block**：SID 标记应紧邻标题或内容块的上方或下方
- **Spec-Item**：使用 `BEGIN/END` 边界标记

### 4.2 Section 和 Block 标注

**标注在标题下方（推荐）**：

```markdown
## 运行视图与时序图
<!-- SID:arch.runtime.sequence -->

端到端LLM调控闭环...
```

**标注在标题上方（可选）**：

```markdown
<!-- SID:arch.runtime.sequence -->
## 运行视图与时序图

端到端LLM调控闭环...
```

### 4.3 Spec-Item 标注（BEGIN/END 边界）

对于需要精确边界的规范项，使用 `BEGIN/END` 标记：

```markdown
<!-- SID:api.rest.create_task BEGIN -->
**Endpoint**: `POST /tasks`

**Request Body**:
```json
{
  "description": "设计一个绑定目标蛋白的肽段",
  "constraints": {...}
}
```

**Response**: `201 Created`，返回 `task_id`
<!-- SID:api.rest.create_task END -->
```

**规则**：

- `BEGIN` 和 `END` 必须成对出现
- `BEGIN` 和 `END` 之间的内容为该 SID 的完整规范范围
- 不允许嵌套 `BEGIN/END` 边界

### 4.4 多行与跨段落标注

如果一个 SID 覆盖多个段落，使用 `BEGIN/END`：

```markdown
<!-- SID:executor.flow.step_execution BEGIN -->
Executor 执行每个 step 时的流程：

1. 从 Plan 中读取 step 定义
2. 根据 tool_name 查找对应的 ToolAdapter
3. 调用 ToolAdapter.execute() 方法
4. 捕获输出并写入 StepResult

注意：如果 step 执行失败，Executor 会记录错误并触发 replan 流程。
<!-- SID:executor.flow.step_execution END -->
```

## 5. 引用规范

### 5.1 SID 引用语法

在文档中引用其他 SID 时，使用以下语法：

```markdown
[ref:SID:<domain>.<topic>.<name>]
```

**示例**：

```markdown
Planner Agent 的候选方案评分机制详见 [ref:SID:planner.algorithm.candidate_scoring]。

关于 FSM 状态转换规则，参考 [ref:SID:fsm.states.transitions]。
```

### 5.2 跨文档引用

SID 引用本身是全局唯一的，无需指定文档名。脚本与工具应能够根据 SID 自动定位到对应文档。

**示例**：

```markdown
<!-- 在 agent-design.md 中引用 architecture.md 的内容 -->
Planner Agent 的状态机行为遵循 [ref:SID:fsm.states.planning] 的定义。
```

### 5.3 Fallback 引用方式

当某些章节尚未分配 SID，或需要引用外部文档时，使用以下 fallback 语法：

```markdown
DOC:<doc_key>#<anchor>
```

**`<doc_key>` 定义**：

| doc_key | 对应文档 |
|---------|----------|
| `arch` | architecture.md |
| `agent` | agent-design.md |
| `impl` | system-implementation-design.md |
| `algo` | core-algorithm-spec.md |
| `tools` | tools-catalog.md |
| `hitl` | hitl-extension.md |
| `test` | test.md |

**`<anchor>` 定义**：

- 对应 Markdown 标题的 slug（小写，空格替换为短横线 `-`）

**示例**：

```markdown
详见 DOC:arch#任务生命周期与状态机

关于工具集成的细节，参考 DOC:tools#executor工具
```

**优先级**：

- **优先使用** `[ref:SID:...]` 语法
- **仅在以下情况使用** `DOC:...` fallback：
  1. 该章节确实尚未分配 SID
  2. 引用外部文档或非本项目文档
  3. 临时引用，计划后续补充 SID

## 6. 禁止项

以下行为**严格禁止**，违反者将导致脚本解析失败或 linting 错误：

### 6.1 禁止重复 SID

**规则**：每个 SID 在整个项目中必须唯一。

**错误示例**：

```markdown
<!-- 在 architecture.md 中 -->
## 状态机设计
<!-- SID:fsm.states.overview -->
...

<!-- 在 system-implementation-design.md 中 -->
## FSM 实现
<!-- SID:fsm.states.overview -->  ❌ 重复 SID
...
```

**检测方式**：

- Linting 工具应扫描所有文档，确保 SID 全局唯一
- 如发现重复，应报告冲突的文件与行号

### 6.2 禁止仅依赖标题文本定位

**规则**：不得仅通过标题文本内容进行章节定位，必须使用 SID 或 `DOC:...#anchor` 方式。

**错误示例**：

```markdown
❌ 详见"任务生命周期与状态机"章节
❌ 参考 architecture.md 的"运行视图与时序图"部分
```

**正确示例**：

```markdown
✓ 详见 [ref:SID:fsm.lifecycle.overview]
✓ 参考 DOC:arch#运行视图与时序图
```

**原因**：

- 标题文本可能被修改，导致引用失效
- SID 提供稳定、可追溯的引用机制

### 6.3 禁止嵌套 BEGIN/END 边界

**规则**：`BEGIN/END` 边界不允许嵌套。

**错误示例**：

```markdown
<!-- SID:outer BEGIN -->
外层内容...

<!-- SID:inner BEGIN -->  ❌ 嵌套的 BEGIN
内层内容...
<!-- SID:inner END -->

外层内容继续...
<!-- SID:outer END -->
```

**解决方式**：

- 使用不同粒度层级（Section → Block → Spec-Item）
- 将嵌套内容拆分为独立的 SID

### 6.4 禁止 SID 格式不合规

**规则**：SID 必须严格遵循 `SID:<domain>.<topic>.<name>` 格式。

**错误示例**：

```markdown
❌ <!-- SID:fsm_states_planning -->  (使用下划线而非点分隔)
❌ <!-- SID:fsm.states -->  (缺少 name 部分)
❌ <!-- SID:FSM.STATES.PLANNING -->  (使用大写)
❌ <!-- SID:fsm.states.planning.detail -->  (超过三级)
```

### 6.5 禁止 BEGIN 缺少对应 END

**规则**：所有 `BEGIN` 标记必须有对应的 `END` 标记。

**错误示例**：

```markdown
<!-- SID:api.rest.create_task BEGIN -->
**Endpoint**: `POST /tasks`
...
<!-- 缺少 END 标记 -->  ❌
```

**检测方式**：

- Linting 工具应检查每个 `BEGIN` 是否有配对的 `END`
- 报告未配对的 SID 及其文件位置

## 7. 验收标准

本契约文档及其实施应满足以下验收标准：

### 7.1 可解析性

- 每一条规则均可被脚本解析为硬性约束
- 提供明确的正则表达式或解析规则，用于提取 SID

**SID 解析正则表达式**：

```regex
<!--\s*SID:([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*)\s*(BEGIN|END)?\s*-->
```

**引用解析正则表达式**：

```regex
\[ref:SID:([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*)\]
```

**Fallback 引用解析正则表达式**：

```regex
DOC:([a-z]+)#([^\s]+)
```

### 7.2 Linting 支持

- 可被 linting 工具直接引用，执行以下检查：
  - SID 格式合规性
  - SID 全局唯一性
  - `BEGIN/END` 配对检查
  - 引用有效性检查（引用的 SID 是否存在）

### 7.3 Docslice 脚本兼容

- `docslice` 脚本应能够：
  - 根据 SID 提取对应的文档片段
  - 支持 Section、Block、Spec-Item 三种粒度
  - 处理 `BEGIN/END` 边界标记
  - 解析引用关系，生成依赖图

### 7.4 Claude Code Skill 集成

- Claude Code 在调用 `docslice` 前，应假定该契约成立
- Skills 应能够通过 SID 查询规范内容，而无需解析整个文档
- 提供明确的 API 或命令行接口，供 Skills 调用

## 8. 附录

### 8.1 示例文档片段

以下是一个完整的文档片段示例，展示了 Section、Block、Spec-Item 的标注方式：

```markdown
## PlannerAgent 接口定义
<!-- SID:planner.interface.overview -->

PlannerAgent 负责解析任务并生成执行计划。

### 输入契约
<!-- SID:planner.interface.input -->

<!-- SID:planner.interface.input.task_schema BEGIN -->
**输入数据结构**: `ProteinDesignTask`

```python
@dataclass
class ProteinDesignTask:
    task_id: str
    description: str
    constraints: Dict[str, Any]
    user_id: Optional[str] = None
```
<!-- SID:planner.interface.input.task_schema END -->

### 输出契约
<!-- SID:planner.interface.output -->

<!-- SID:planner.interface.output.plan_schema BEGIN -->
**输出数据结构**: `Plan`

```python
@dataclass
class Plan:
    plan_id: str
    steps: List[Step]
    metadata: Dict[str, Any]
```
<!-- SID:planner.interface.output.plan_schema END -->

### 约束条件
<!-- SID:planner.interface.constraints -->

<!-- SID:planner.interface.constraints.timeout BEGIN -->
- Planner 必须在 30 秒内返回初始计划
- 如超时，系统应返回 `TIMEOUT` 错误
<!-- SID:planner.interface.constraints.timeout END -->

相关规范详见 [ref:SID:planner.algorithm.candidate_scoring]。
```

### 8.2 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0 | 2025-12-31 | 初始版本，定义 SID 格式、粒度、标注方式、引用规范与禁止项 |

---

**本文档是 Milestone "Addressable Design Docs & Spec Retrieval Skill" 的基础法律文本，任何修改应通过正式的 PR 流程并更新版本历史。**
