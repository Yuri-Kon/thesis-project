# 测试文档

本目录包含项目的测试套件，按照专业的测试方法组织。

## 目录结构

```
tests/
├── __init__.py
├── conftest.py          # 共享fixtures和测试工具
├── unit/                # 单元测试
│   ├── test_planner_agent.py
│   ├── test_executor_agent.py
│   ├── test_summarizer_agent.py
│   ├── test_contracts.py
│   └── test_db.py
├── integration/         # 集成测试
│   └── test_workflow.py
└── api/                 # API测试
    └── test_api_endpoints.py
```

## 测试分类

### 单元测试 (Unit Tests)

- **位置**: `tests/unit/`
- **标记**: `@pytest.mark.unit`
- **目的**: 测试单个组件或函数的独立功能
- **覆盖范围**:
  - Agents (Planner, Executor, Summarizer)
  - 数据模型 (Contracts, DB models)
  - 工具函数

### 集成测试 (Integration Tests)

- **位置**: `tests/integration/`
- **标记**: `@pytest.mark.integration`
- **目的**: 测试多个组件协同工作的场景
- **覆盖范围**:
  - 完整工作流执行
  - 组件间交互

### API测试 (API Tests)

- **位置**: `tests/api/`
- **标记**: `@pytest.mark.api`
- **目的**: 测试HTTP API端点
- **覆盖范围**:
  - FastAPI端点
  - 请求/响应验证
  - 错误处理

## 运行测试

### 安装依赖

```bash
pip install -r requirements.txt
pip install httpx  # FastAPI TestClient需要
```

### 运行所有测试

```bash
pytest
```

### 运行特定类型的测试

```bash
# 只运行单元测试
pytest -m unit

# 只运行集成测试
pytest -m integration

# 只运行API测试
pytest -m api
```

### 运行特定测试文件

```bash
pytest tests/unit/test_planner_agent.py
```

### 运行特定测试类或函数

```bash
pytest tests/unit/test_planner_agent.py::TestPlannerAgent
pytest tests/unit/test_planner_agent.py::TestPlannerAgent::test_plan_creates_plan_with_correct_task_id
```

### 详细输出

```bash
pytest -v  # 详细模式
pytest -vv  # 更详细
pytest -s  # 显示print输出
```

### 覆盖率报告（如果安装了pytest-cov）

```bash
pip install pytest-cov
pytest --cov=src --cov-report=html
```

## 测试Fixtures

共享的测试fixtures定义在 `conftest.py` 中：

- `sample_task`: 示例ProteinDesignTask
- `sample_plan`: 示例Plan
- `sample_workflow_context`: 示例WorkflowContext
- `sample_step_result`: 示例StepResult
- `sample_design_result`: 示例DesignResult
- `temp_report_dir`: 临时报告目录
- `mock_executor`, `mock_planner`, `mock_summarizer`: Mock对象

## 测试最佳实践

1. **独立性**: 每个测试应该独立运行，不依赖其他测试的状态
2. **可重复性**: 测试应该在任何环境下都能重复运行
3. **清晰性**: 测试名称应该清楚地描述测试的内容
4. **快速性**: 单元测试应该快速执行
5. **覆盖性**: 尽量覆盖各种边界情况和错误情况

## 配置

测试配置在 `pytest.ini` 文件中：

- 测试路径: `tests/`
- 输出选项: 详细模式，简短回溯
- 标记定义: unit, integration, api, slow

## 注意事项

1. 某些测试可能依赖外部资源（如文件系统），使用 `tmp_path` fixture 创建临时目录
2. API测试使用FastAPI的TestClient，不需要实际启动服务器
3. 集成测试可能运行较慢，可以使用 `@pytest.mark.slow` 标记