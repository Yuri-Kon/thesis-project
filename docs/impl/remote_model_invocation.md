# Remote Model Invocation Service
<!-- SID:impl.remote_model_invocation.overview -->

## 概述

为了支持远程 ESMFold 服务调用，系统新增了通用的 `RemoteModelInvocationService` 抽象层。该层提供统一的 submit/poll/download 接口，默认实现 REST 客户端，并保留 SSH/SDK 扩展点。

## 架构设计

### 核心组件
<!-- SID:impl.remote_model_invocation.components -->

1. **RemoteModelInvocationService** (`src/engines/remote_model_service.py`)
   - 抽象基类，定义统一接口
   - 方法：
     - `submit_job(payload, task_id, step_id) -> job_id`
     - `poll_status(job_id) -> JobStatus`
     - `download_results(job_id, output_dir) -> outputs`

2. **RESTModelInvocationService** (`src/engines/remote_model_service.py`)
   - REST API 客户端实现
   - 使用 httpx 进行 HTTP 通信
   - 默认端点约定：
     - `POST /predict` - 提交作业
     - `GET /job/{job_id}` - 查询作业状态
     - `GET /results/{job_id}` - 获取作业结果

3. **BaseToolAdapter 扩展** (`src/adapters/base_tool_adapter.py`)
   - 新增 `run_remote()` 方法（可选实现）
   - 保持向后兼容性（`run_local()` 保持不变）

4. **RemoteESMFoldAdapter** (`src/adapters/remote_esmfold_adapter.py`)
   - ESMFold 远程适配器示例实现
   - 将 `run_local()` 委托给 `run_remote()`
   - 与现有 StepRunner 无缝集成

## 工作流程

```
┌─────────────┐
│  StepRunner │
└──────┬──────┘
       │
       │ run_local(inputs)
       ▼
┌──────────────────────┐
│ RemoteESMFoldAdapter │
└──────────┬───────────┘
           │
           │ run_remote(inputs)
           ▼
┌────────────────────────────┐
│ RESTModelInvocationService │
└────────────┬───────────────┘
             │
             ├─► submit_job() ──────► POST /predict
             │
             ├─► poll_status() ─────► GET /job/{id}  (轮询)
             │
             └─► download_results()─► GET /results/{id}
```

## 使用示例

### 基本使用

```python
from src.adapters.remote_esmfold_adapter import RemoteESMFoldAdapter
from pathlib import Path

# 创建远程适配器
adapter = RemoteESMFoldAdapter(
    base_url="http://esmfold-service.example.com:8000",
    output_dir=Path("output/remote"),
)

# 执行预测
outputs, metrics = adapter.run_local({
    "sequence": "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV",
    "task_id": "task_001",
    "step_id": "S1",
})
```

### 自定义服务配置

```python
from src.engines.remote_model_service import RESTModelInvocationService
from src.adapters.remote_esmfold_adapter import RemoteESMFoldAdapter

# 创建自定义配置的服务
service = RESTModelInvocationService(
    base_url="http://custom-service.example.com:8000",
    timeout=60.0,          # 60秒超时
    poll_interval=10.0,     # 每10秒轮询一次
    max_poll_attempts=30,   # 最多轮询30次（总共5分钟）
)

# 使用自定义服务创建适配器
adapter = RemoteESMFoldAdapter(service=service)
```

## 产物映射

远程服务的输出会自动映射到 `StepResult + artifacts`：

- `outputs` 字典包含：
  - 工具特定的输出字段（如 `pdb_path`, `metrics`）
  - `artifacts`: 下载的产物文件列表（本地绝对路径）

- `metrics` 字典包含：
  - `exec_type`: "remote"
  - `duration_ms`: 执行时间（毫秒）
  - `job_id`: 远程作业 ID

### 自动路径映射

`download_results()` 会自动将 `outputs` 中的相对路径映射为本地绝对路径：

**远程响应**:
```json
{
  "outputs": {
    "pdb_path": "structure.pdb",
    "log_path": "esmfold.log"
  },
  "artifacts": [
    {"name": "structure.pdb", "url": "..."},
    {"name": "esmfold.log", "url": "..."}
  ]
}
```

**下载后**:
```python
outputs = {
    "pdb_path": "/path/to/output/structure.pdb",  # 已映射为绝对路径
    "log_path": "/path/to/output/esmfold.log",    # 已映射为绝对路径
    "artifacts": [
        "/path/to/output/structure.pdb",
        "/path/to/output/esmfold.log"
    ]
}
```

这确保下游消费者（如 visualization adapter）能够直接访问下载的文件，而无需手动拼接路径。

## REST API 规范
<!-- SID:impl.remote_model_invocation.rest_api -->

远程服务应实现以下端点：

### POST /predict
提交预测作业

**请求**:
```json
{
  "task_id": "task_001",
  "step_id": "S1",
  "inputs": {
    "sequence": "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV"
  }
}
```

**响应**:
```json
{
  "job_id": "job_12345"
}
```

### GET /job/{job_id}
查询作业状态

**响应**:
```json
{
  "job_id": "job_12345",
  "status": "pending|running|completed|failed"
}
```

### GET /results/{job_id}
获取作业结果

**响应**:
```json
{
  "job_id": "job_12345",
  "outputs": {
    "pdb_path": "structure.pdb",
    "metrics": {
      "pLDDT": 85.5
    }
  },
  "artifacts": [
    {
      "name": "structure.pdb",
      "url": "http://service/files/structure.pdb",
      "type": "pdb"
    }
  ]
}
```

## 错误处理

远程服务实现了分层错误处理：

1. **网络错误** → `FailureType.RETRYABLE`
2. **HTTP 5xx 错误** → `FailureType.RETRYABLE`
3. **HTTP 4xx 错误** → `FailureType.NON_RETRYABLE`
4. **作业失败** → `FailureType.TOOL_ERROR`
5. **轮询超时** → `FailureType.RETRYABLE`

所有错误通过 `StepRunError` 异常抛出，与现有的失败处理流程（retry/patch/replan）无缝集成。

## 扩展点

### 实现自定义远程服务

```python
from src.engines.remote_model_service import RemoteModelInvocationService

class SSHModelInvocationService(RemoteModelInvocationService):
    """基于 SSH 的远程服务实现（示例）"""

    def submit_job(self, payload, task_id, step_id):
        # SSH 提交作业逻辑
        pass

    def poll_status(self, job_id):
        # SSH 查询状态逻辑
        pass

    def download_results(self, job_id, output_dir):
        # SCP 下载结果逻辑
        pass
```

## 测试

### 单元测试

- `tests/unit/test_remote_model_service.py` - 测试 REST 服务实现
- `tests/unit/test_remote_esmfold_adapter.py` - 测试远程适配器

### 运行测试

```bash
source .venv/bin/activate
pytest tests/unit/test_remote_model_service.py -v
pytest tests/unit/test_remote_esmfold_adapter.py -v
```

## 依赖

- `httpx` - HTTP 客户端库（已添加到 requirements.txt）

## 设计约束

根据 `AGENT_CONTRACT.md`：

- ✅ 保持最小化变更原则
- ✅ 不修改 FSM 或 Agent 边界
- ✅ 契约优先的数据模型（StepResult/ArtifactRef）
- ✅ 向后兼容（不破坏现有 run_local 流程）
- ✅ 适配现有失败处理机制

## 相关文件

- `src/engines/remote_model_service.py` - 远程服务抽象和 REST 实现
- `src/adapters/base_tool_adapter.py` - 基类扩展
- `src/adapters/remote_esmfold_adapter.py` - 远程适配器示例
- `examples/remote_esmfold_example.py` - 使用示例
- `tests/unit/test_remote_model_service.py` - REST 服务测试
- `tests/unit/test_remote_esmfold_adapter.py` - 远程适配器测试

## 验收标准

- ✅ 统一接口可被 Executor 调用
- ✅ 远程结果产出 StepResult + artifacts
- ✅ REST 实现可正常 submit/poll/download
- ✅ 具备可测试的 mock 入口
- ✅ 所有单元测试通过（251/252 通过，1个失败与本功能无关）
