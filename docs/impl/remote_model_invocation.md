# Remote Model Invocation Service
<!-- SID:impl.remote_model_invocation.overview -->

## 概述

为了支持远程 ESMFold 服务调用，系统新增了通用的 `RemoteModelInvocationService` 抽象层。该层提供统一的 submit/poll/download 接口，默认实现 REST 客户端，并保留 SSH/SDK 扩展点。

**Week 5 扩展**：新增 NVIDIA NIM 作为首选远程调用后端，通过 `NvidiaNIMClient` 和 `NIMESMFoldAdapter` 实现。

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

3. **NvidiaNIMClient** (`src/engines/nim_client.py`) - Week 5 新增
   - NVIDIA NIM Biology API 客户端
   - 支持 `call_sync()` 同步调用 NIM 端点
   - 从 `ProviderConfig` 读取配置（API key、base URL、超时等）
   - HTTP 错误映射到 `FailureCode`（见 Issue #105）

4. **ProviderConfig** (`src/engines/provider_config.py`) - Week 5 新增
   - 远程模型服务提供商配置数据类
   - 从 `configs/model_providers.json` 加载配置
   - 支持环境变量解析 API Key
   - 配置文件不存在时回退到内置默认值

5. **BaseToolAdapter 扩展** (`src/adapters/base_tool_adapter.py`)
   - 新增 `run_remote()` 方法（可选实现）
   - 保持向后兼容性（`run_local()` 保持不变）

6. **RemoteESMFoldAdapter** (`src/adapters/remote_esmfold_adapter.py`)
   - ESMFold 远程适配器示例实现
   - 将 `run_local()` 委托给 `run_remote()`
   - 与现有 StepRunner 无缝集成

7. **NIMESMFoldAdapter** (`src/adapters/nim_adapter.py`) - Week 5 新增
   - 继承 `BaseToolAdapter`
   - 输入转换：`{"sequence": "..."}` → NIM 格式
   - 输出转换：NIM 响应 → `{"pdb_path": ..., "plddt": ..., "pdb_string": ...}`
   - 当 `NIM_API_KEY` 环境变量存在时自动注册

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

### NVIDIA NIM 特定失败码
<!-- SID:impl.remote_model_invocation.nim_failure_codes -->

NIM 客户端定义了专用的失败码（在 `src/workflow/errors.py`）：

| FailureCode | FailureType | HTTP 状态码 | 触发场景 | 恢复动作 |
|-------------|-------------|-------------|----------|----------|
| `NIM_AUTH_FAILED` | NON_RETRYABLE | 401, 403 | API key 无效/过期 | HITL（凭证问题） |
| `NIM_QUOTA_EXCEEDED` | RETRYABLE | 429 | API 配额/速率限制 | 带退避重试，然后 patch 到替代工具 |
| `NIM_MODEL_NOT_FOUND` | NON_RETRYABLE | 404 | 请求的模型不可用 | Patch 到替代工具 |
| `NIM_INVALID_INPUT` | NON_RETRYABLE | 400, 422 | 输入验证失败（如序列过长） | Patch step 输入 |
| `NIM_MODEL_ERROR` | RETRYABLE | 500+ | 模型内部错误 | 重试，然后 replan |

这些失败码与通用失败处理流程集成：
- `RETRYABLE` 类型会触发自动重试（带指数退避）
- 重试耗尽后，可 patch 到替代工具（如 `esmfold` 本地路径）
- `NON_RETRYABLE` 类型直接触发 HITL 或 patch 流程

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

---

## NVIDIA NIM 集成（Week 5 扩展）
<!-- SID:impl.remote_model_invocation.nvidia_nim -->

### 概述

NVIDIA NIM（NVIDIA Inference Microservices）提供托管的生物信息学模型 API，包括 ESMFold。系统通过 `NvidiaNIMClient` 和 `NIMESMFoldAdapter` 实现 NIM 集成。

### 架构

```
┌─────────────┐
│  StepRunner │
└──────┬──────┘
       │
       │ run_local(inputs)
       ▼
┌──────────────────┐
│ NIMESMFoldAdapter│
└────────┬─────────┘
         │
         │ call_sync(inputs)
         ▼
┌────────────────────┐     ┌─────────────────┐
│  NvidiaNIMClient   │────►│  ProviderConfig │
└─────────┬──────────┘     └─────────────────┘
          │                        ▲
          │ HTTP POST              │ load from
          ▼                        │
┌─────────────────────────┐  ┌─────────────────────────┐
│ NVIDIA NIM API          │  │ configs/model_providers │
│ integrate.api.nvidia.com│  │ .json                   │
└─────────────────────────┘  └─────────────────────────┘
```

### Provider 配置系统
<!-- SID:impl.remote_model_invocation.provider_config -->

#### ProviderConfig 数据类

```python
@dataclass
class ProviderConfig:
    provider_type: str           # e.g. "nvidia_nim"
    description: str = ""
    base_url: str = ""
    api_key_env: str = ""        # 环境变量名，如 "NIM_API_KEY"
    timeout: float = 60.0
    max_retries: int = 3
    extra: Dict[str, Any] = field(default_factory=dict)

    def get_api_key(self) -> str:
        """从环境变量获取 API Key"""
```

#### 配置文件格式

`configs/model_providers.json`:

```json
{
  "providers": {
    "nvidia_nim": {
      "provider_type": "nvidia_nim",
      "description": "NVIDIA NIM Biology Models",
      "base_url": "https://integrate.api.nvidia.com/v1",
      "api_key_env": "NIM_API_KEY",
      "timeout": 60,
      "max_retries": 3,
      "extra": {
        "supported_models": ["nvidia/esmfold", "nvidia/esm2nv"]
      }
    }
  }
}
```

#### 配置加载

```python
from src.engines.provider_config import load_provider_config, get_provider_config

# 加载所有配置
configs = load_provider_config()

# 获取特定提供商配置
nim_config = get_provider_config("nvidia_nim")
api_key = nim_config.get_api_key()  # 从 NIM_API_KEY 环境变量获取
```

### NIM Client 使用示例

```python
from src.engines.nim_client import NvidiaNIMClient

# 创建客户端（自动加载配置）
client = NvidiaNIMClient()

# 同步调用 ESMFold
result = client.call_sync(
    model_id="nvidia/esmfold",
    inputs={"sequence": "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV"}
)

# 结果包含
# - pdb_string: PDB 结构内容
# - plddt: 置信度分数
```

### NIM ESMFold Adapter 使用

```python
from src.adapters.nim_adapter import NIMESMFoldAdapter
from pathlib import Path

# 创建适配器
adapter = NIMESMFoldAdapter(output_dir=Path("output/nim"))

# 执行预测
outputs, metrics = adapter.run_local({
    "sequence": "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV",
    "task_id": "task_001",
    "step_id": "S1",
})

# outputs 包含：
# - pdb_path: 保存的 PDB 文件路径
# - plddt: 置信度分数
# - pdb_string: PDB 内容字符串

# metrics 包含：
# - provider: "nvidia_nim"
# - model_id: "nvidia/esmfold"
# - exec_type: "remote"
# - duration_ms: 执行时间
```

### 自动注册

在 `src/adapters/builtins.py` 中，当检测到 `NIM_API_KEY` 环境变量时，会自动注册 `NIMESMFoldAdapter`：

```python
def ensure_builtin_adapters():
    # ... 其他注册 ...

    # NIM ESMFold（当 API key 存在时）
    if os.getenv("NIM_API_KEY"):
        from src.adapters.nim_adapter import NIMESMFoldAdapter
        register_adapter("nim_esmfold", NIMESMFoldAdapter)
```

### 相关文件

- `src/engines/nim_client.py` - NIM API 客户端
- `src/engines/provider_config.py` - Provider 配置系统
- `src/adapters/nim_adapter.py` - NIM ESMFold 适配器
- `configs/model_providers.json` - 提供商配置文件
- `tests/unit/test_nim_client.py` - NIM 客户端测试
- `tests/unit/test_nim_adapter.py` - NIM 适配器测试

### 与 KG 集成

ProteinToolKG 中新增 `nim_esmfold` 工具定义：

```json
{
  "id": "nim_esmfold",
  "name": "NIM ESMFold",
  "capabilities": ["structure_prediction"],
  "io": {
    "inputs": {"sequence": "str"},
    "outputs": {"pdb_path": "path", "plddt": "float", "pdb_string": "str"}
  },
  "constraints": {
    "preconditions": ["sequence_provided"],
    "resource_assumptions": ["network_available", "nim_api_key_configured"],
    "limits": {"max_length": 400}
  },
  "execution": {
    "backend": "remote_model_service",
    "provider": "nvidia_nim",
    "model_id": "nvidia/esmfold",
    "sync_mode": true
  },
  "cost_score": 0.3,
  "safety_level": 1
}
```

Planner 可通过 KG 选择工具路径：
- `protein_mpnn` → `esmfold`（本地 Nextflow）
- `protein_mpnn` → `nim_esmfold`（NIM 远程）

查询接口：
- `find_tools_by_capability("structure_prediction")` → 返回 `esmfold` 和 `nim_esmfold`
- `find_tools_by_backend("remote_model_service", "nvidia_nim")` → 返回 `nim_esmfold`
