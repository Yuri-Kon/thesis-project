# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

这是一个**基于 LLM 驱动的蛋白质设计多智能体系统**(毕业论文项目)，采用有限状态机(FSM)管理任务生命周期，支持重试→修补→重新规划的失败恢复机制，以及可选的人机交互(HITL)检查点。

系统核心特性：
- **FSM 驱动**：任务生命周期由固定状态机控制，状态转换必须显式、可记录、可审计
- **契约优先**：所有数据模型(Pydantic schemas)是稳定契约，向后兼容
- **严格角色分离**：四个 Agent 各司其职，互不越权
- **失败处理即控制流**：retry → patch → replan 是结构化流程，非异常处理

## 设计文档位置

设计规范位于独立 worktree 的 `design` 分支，默认路径：`../thesis-project.design/docs/design/`

**在修改系统行为或结构前，必须先查阅以下文档**（按优先级）：
1. `architecture.md` - 总体架构
2. `agent-design.md` - Agent 职责边界
3. `system-implementation-design.md` - 实现细节
4. `core-algorithm-spec.md` - 核心算法规范
5. `tools-catalog.md` - 工具目录

**关键原则**：代码行为与文档冲突时，**文档优先**。

同时，代码库根目录的 `AGENTS.md` 是面向自动化 Agent 的契约执行指南，包含：
- 系统不变量(System Invariants)
- Agent 职责边界
- 数据模型契约
- 安全默认策略

## 常用开发命令

### 测试

```bash
# 运行所有测试
pytest tests/ -v

# 按类型运行测试
pytest tests/unit/ -v -m unit           # 单元测试
pytest tests/integration/ -v -m integration  # 集成测试
pytest tests/api/ -v -m api             # API 测试

# 运行单个测试文件
pytest tests/unit/test_planner.py -v

# 运行单个测试函数
pytest tests/unit/test_planner.py::test_plan_with_status -v

# 带覆盖率报告
pytest tests/ --cov=src --cov-report=html
# 结果输出到 htmlcov/index.html

# 使用快捷脚本
./run_tests.sh  # 依次运行所有、单元、集成、API 测试
```

### 启动 API 服务器

```bash
# 开发模式（带热重载）
uvicorn src.api.main:app --reload --port 8000

# 访问 API 文档
# http://localhost:8000/docs
```

### 依赖管理

```bash
# 安装依赖
pip install -r requirements.txt

# 激活虚拟环境（如果使用 venv）
source .venv/bin/activate
```

## 系统架构核心概念

### 1. 有限状态机（FSM）

任务状态分为**外部状态**(面向用户)和**内部状态**(执行细节)：

**外部状态流转**：
```
CREATED → PLANNING → WAITING_PLAN_CONFIRM → PLANNED → RUNNING →
  WAITING_PATCH_CONFIRM → WAITING_REPLAN_CONFIRM → SUMMARIZING →
  DONE/FAILED/CANCELLED
```

**关键内部状态**：
- `WAITING_PATCH`, `PATCHING` - 修补流程
- `WAITING_REPLAN`, `REPLANNING` - 重新规划流程

**状态转换**：
- 由 `src/workflow/status.py:transition_task_status()` 强制校验
- 所有转换记录到 `/data/logs/{task_id}.jsonl`
- 终态（DONE/FAILED/CANCELLED）不可变

### 2. 四大 Agent 及职责边界

| Agent | 职责 | 禁止行为 |
|------|------|---------|
| **PlannerAgent** | 解析任务目标，查询 KG，生成 Plan/Patch/Replan | 执行工具、修改运行时状态 |
| **ExecutorAgent** | 执行步骤，管理重试/修补/重规划流程 | 更改任务目标、发明新 schema |
| **SafetyAgent** | 评估风险，发出 ok/warn/block 决策 | 执行工具、修改计划 |
| **SummarizerAgent** | 汇总结果，生成报告 | 重新运行工具、覆盖安全决策 |

**核心原则**：
- PlannerAgent 只生成计划，不执行
- ExecutorAgent 是唯一执行工具的组件
- SafetyAgent 只做风险评估，不修改数据流
- SummarizerAgent 只做后处理，不影响执行

### 3. 执行流程（Plan Execution）

```
ProteinDesignTask
    ↓
PlannerAgent.plan() → Plan
    ↓
ExecutorAgent.run_plan()
    ↓
    ├→ PlanRunner.run_plan() [PLANNED → RUNNING]
    │   ├→ SafetyAgent.check_task_input() [前置检查]
    │   ├→ StepRunner.run_step() × N [逐步执行]
    │   │   ├→ SafetyAgent.check_pre_step()
    │   │   ├→ Adapter.run_local() [via AdapterRegistry]
    │   │   └→ SafetyAgent.check_post_step()
    │   │       ↓ (失败时)
    │   │   PatchRunner.run_step_with_patch()
    │   │       ├→ PlannerAgent.patch() [生成补丁]
    │   │       └→ [可选 HITL PendingAction]
    │   └→ SafetyAgent.check_final_result() [后置检查]
    │
    └→ SummarizerAgent.summarize() [SUMMARIZING → DONE]
        ↓
    DesignResult → /nf/output/reports/
```

**重试 → 修补 → 重规划策略**：
1. **Retry**：StepRunner 内置重试循环（默认最多 2 次），仅对 `FailureType.RETRYABLE` 生效
2. **Patch**：重试耗尽后，PatchRunner 调用 PlannerAgent.patch() 生成局部修正
3. **Replan**：Patch 失败或 Safety 阻断后，触发完整重新规划

### 4. 数据契约（Core Contracts）

所有核心模型定义在 `src/models/contracts.py`，包括：

**任务与计划**：
- `ProteinDesignTask` - 输入任务
- `Plan`, `PlanStep` - 完整计划与单步骤
- `PlanPatch`, `PlanPatchOp` - 补丁操作

**执行结果**：
- `StepResult` - 单步执行结果（含 status/failure_type/outputs/metrics）
- `DesignResult` - 最终输出（sequence/scores/report_path）

**安全与风险**：
- `RiskFlag` - 风险标记（level: ok/warn/block）
- `SafetyResult` - 安全检查结果

**人机交互**：
- `PendingAction` - 等待人类决策（PLAN_CONFIRM/PATCH_CONFIRM/REPLAN_CONFIRM）
- `Decision` - 人类决策（ACCEPT/REPLAN/CONTINUE/CANCEL）

**恢复快照**：
- `TaskSnapshot` - 最小恢复上下文

**修改契约的规则**：
- **禁止**删除或重命名已有字段
- **禁止**改变字段语义
- **允许**通过 `metadata`/`metrics` 或可选字段扩展
- 步骤引用（如 `"S1.sequence"`）是契约的一部分，必须在适配器/执行逻辑中解析

### 5. 适配器系统（Tool Adapters）

**抽象接口** (`src/adapters/base_tool_adapter.py`)：
```python
class BaseToolAdapter(ABC):
    tool_id: str
    adapter_id: str | None

    def resolve_inputs(step: PlanStep, context: WorkflowContext) -> Dict
    def run_local(inputs: Dict) -> Tuple[Dict, Dict]  # (outputs, metrics)
```

**注册与查找** (`src/adapters/registry.py`)：
- `AdapterRegistry.get_adapter(tool_id)` - 按 tool_id 或 adapter_id 查找
- `register_adapter(adapter)` - 运行时注册
- `ensure_builtin_adapters()` - 注册内置适配器

**现有适配器**：
- `DummyAdapter` - 测试用 mock 工具
- `ESMFoldAdapter`, `ProteinMPNNAdapter`, `RDKitPropsAdapter` - 占位符（待实现）

**新增工具的步骤**：
1. 在 `src/tools/<tool_name>/` 创建工具逻辑
2. 创建 `src/tools/<tool_name>/adapter.py` 继承 `BaseToolAdapter`
3. 实现 `resolve_inputs()` 和 `run_local()`
4. 在 `src/adapters/builtins.py` 中注册

### 6. 失败分类与错误处理

`src/workflow/errors.py` 定义 `FailureType` 枚举：
- `RETRYABLE` - 可重试（如 timeout）
- `NON_RETRYABLE` - 跳过重试，直接进入 patch（如 ValueError）
- `TOOL_ERROR` - 工具通用错误
- `SAFETY_BLOCK` - 安全阻断（特殊处理）

`classify_exception(exc)` 将异常映射到 FailureType。

**异常层次**：
```
RunnerError (基类)
  ├→ StepRunError (步骤级)
  └→ PlanRunError (计划级，带 step_id)
```

### 7. WorkflowContext（运行时上下文）

`src/workflow/context.py` 定义执行期间的全局状态：

```python
class WorkflowContext:
    task: ProteinDesignTask
    plan: Optional[Plan]
    step_results: Dict[str, StepResult]
    safety_events: List[SafetyResult]
    design_result: Optional[DesignResult]
    pending_action: Optional[PendingAction]
    status: InternalStatus
```

**常用方法**：
- `add_step_result(result)` - 记录步骤结果
- `get_step_output(step_id, key)` - 获取步骤输出（用于引用解析）
- `has_step_result(step_id)` - 检查步骤是否已执行

## 项目结构概览

```
src/
  agents/          - 四大 Agent 实现
    planner.py     - 规划器（生成 Plan/Patch/Replan）
    executor.py    - 执行器（编排 Runner）
    safety.py      - 安全检查（多阶段风险评估）
    summarizer.py  - 汇总器（生成 DesignResult）

  workflow/        - 执行编排与控制流
    workflow.py    - 主入口（run_task_sync）
    plan_runner.py - 完整计划执行
    step_runner.py - 单步执行（含重试）
    patch_runner.py - 修补工作流
    status.py      - FSM 状态转换
    errors.py      - 失败分类
    context.py     - 运行时上下文
    pending_action.py - HITL 动作创建
    decision_apply.py - HITL 决策应用
    patch.py       - 补丁操作
    snapshots.py   - 快照创建

  models/          - 数据契约
    contracts.py   - 核心 schema（Plan/StepResult/SafetyResult/等）
    db.py          - 持久化模型（TaskRecord/StepRecord）
    validation.py  - 决策验证

  adapters/        - 工具适配器基础设施
    base_tool_adapter.py - 抽象接口
    registry.py    - 适配器注册表
    dummy_adapter.py - 测试适配器
    builtins.py    - 内置适配器注册

  tools/           - 具体工具实现（每个工具一个子目录）
    visualization/ - 可视化工具

  api/             - FastAPI 端点
    main.py        - POST /tasks, GET /tasks/{task_id}

  storage/         - 持久化工具
  kg/              - 知识图谱客户端

tests/
  conftest.py      - 共享 fixtures（sample_task/sample_plan/等）
  unit/            - 单元测试（26 个文件）
  integration/     - 集成测试
  api/             - API 测试

data/
  logs/            - 任务事件日志（{task_id}.jsonl）

output/, nf/output/
  reports/         - 任务报告输出
```

## 测试模式

### 共享 Fixtures (`tests/conftest.py`)

- `sample_task` - ProteinDesignTask 示例
- `sample_plan` - 包含单个 dummy_tool 步骤的 Plan
- `sample_workflow_context` - WorkflowContext
- `sample_step_result` - StepResult
- `sample_design_result` - DesignResult
- `mock_executor`, `mock_planner`, `mock_summarizer` - Agent mocks

### 测试分类标记

- `@pytest.mark.unit` - 单元测试
- `@pytest.mark.integration` - 集成测试
- `@pytest.mark.api` - API 测试
- `@pytest.mark.slow` - 慢速测试

### 典型测试模式

**适配器注册测试**：
```python
def test_adapter_registration():
    ADAPTER_REGISTRY.clear()  # 清空注册表
    adapter = DummyAdapter()
    ADAPTER_REGISTRY.register(adapter)
    assert ADAPTER_REGISTRY.get("dummy_tool") == adapter
```

**StepRunner 重试测试**：
```python
@patch("time.sleep")  # Mock sleep 避免实际延迟
def test_step_retry_logic(mock_sleep, sample_plan, sample_workflow_context):
    # ... 测试重试逻辑
```

**状态转换测试**：
```python
def test_fsm_transitions():
    # 验证合法转换
    transition_task_status(InternalStatus.CREATED, InternalStatus.PLANNING)

    # 验证非法转换抛出异常
    with pytest.raises(ValueError):
        transition_task_status(InternalStatus.DONE, InternalStatus.RUNNING)
```

## 代码修改原则

### 系统不变量（绝对禁止违反）

1. **FSM 是真理源**
   - 禁止发明新状态（除非用户明确要求且更新设计文档）
   - 禁止隐式或越权修改任务状态
   - 所有状态转换必须：显式、可记录、API/DB/日志一致

2. **严格角色分离**
   - PlannerAgent：生成 Plan/Patch/Replan，禁止执行工具或修改运行时
   - ExecutorAgent：唯一可执行工具的组件，处理重试/修补/重规划
   - SafetyAgent：仅评估风险并发出结果，禁止修改计划或输出
   - SummarizerAgent：仅汇总结果和生成报告，禁止重新运行工具或覆盖安全决策

3. **契约优先数据模型**
   - 禁止重命名或删除已有字段
   - 禁止改变字段语义
   - 扩展必须通过 `metadata`/`metrics` 或可选字段
   - 步骤引用（如 `"S1.sequence"`）是契约的一部分，必须在适配器/执行逻辑中解析

4. **失败处理是控制流，非异常**
   - 步骤失败不等于任务失败
   - 预期顺序：retry（有界，带回退）→ patch（局部修改）→ replan（重新生成后缀）
   - 仅不可恢复的失败或永久安全阻断导致 FAILED

### 安全默认策略（不确定时遵循）

- **优先最小保守修改**
- **禁止**引入新 FSM 状态
- **禁止**将执行逻辑移入 Planner/Safety/Summarizer
- 集中引用解析逻辑（adapters/step runner）
- 添加测试锁定和文档化所选行为

### 修改行为时必须更新测试

涵盖以下场景：
- FSM 状态转换（断言合法转换，禁止非法转换）
- 契约变更（schema 级测试，消费者兼容性测试）
- 重试/修补/重规划逻辑（有界重试+回退，补丁应用+重执行，前缀锁定正确性）

## 日志与审计

**结构化日志字段**：
- `task_id`, `step_id`, `plan_version`, `state`, `event`
- 日志必须与 FSM 状态和任务快照保持一致
- **禁止记录机密**（API 密钥、令牌、凭证）

**日志位置**：
- `/data/logs/{task_id}.jsonl` - 任务事件日志
- `/nf/output/reports/` - 任务报告

## 常见开发任务场景

### 添加新工具适配器

1. 创建 `src/tools/<tool_name>/` 目录
2. 实现工具逻辑（Python 脚本或调用外部 API）
3. 创建 `src/tools/<tool_name>/adapter.py`：
   ```python
   from src.adapters.base_tool_adapter import BaseToolAdapter

   class MyToolAdapter(BaseToolAdapter):
       tool_id = "my_tool"

       def resolve_inputs(self, step, context):
           # 解析输入，包括引用（如 "S1.sequence"）
           return {...}

       def run_local(self, inputs):
           # 执行工具
           outputs = {...}
           metrics = {...}
           return outputs, metrics
   ```
4. 在 `src/adapters/builtins.py` 注册
5. 添加单元测试到 `tests/unit/test_adapters.py`

### 修改 Agent 行为

1. **先查阅设计文档** (`../thesis-project.design/docs/design/`)
2. 确认修改不违反角色边界（参考 AGENTS.md）
3. 修改对应 Agent 文件（`src/agents/<agent>.py`）
4. **必须**添加或更新测试覆盖新行为
5. 如有状态转换变化，更新 `src/workflow/status.py` 和测试

### 扩展数据契约

1. 在 `src/models/contracts.py` 中修改模型
2. **仅允许**添加可选字段或扩展 `metadata`/`metrics`
3. 运行所有测试确保向后兼容
4. 更新相关的 `tests/conftest.py` fixtures

### 调试执行流程

1. 检查日志：`/data/logs/{task_id}.jsonl`
2. 使用 `WorkflowContext` 的 `step_results` 和 `safety_events`
3. 在 `StepRunner` 或 `PlanRunner` 添加日志点
4. 使用 `pytest -v -s` 查看标准输出

## API 使用示例

### 创建任务

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "设计一个与目标蛋白结合的小肽",
    "constraints": {"max_length": 20},
    "metadata": {"creator": "user123"}
  }'
```

### 查询任务状态

```bash
curl http://localhost:8000/tasks/{task_id}
```

响应包含 `TaskRecord`，含 `external_status`, `design_result` 等字段。

## 语言规范

- **用户交流**：中文
- **代码与注释**：可使用英文
- **文档字符串**：中文优先，技术术语可用英文
- **日志消息**：中文，包含必要的英文字段名

## 版本控制策略

- `master` - 主分支（稳定版本）
- `dev` - 开发分支（当前工作）
- `design` - 设计文档分支（独立 worktree）

提交前运行测试：`pytest tests/ -v`
