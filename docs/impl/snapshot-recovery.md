# Snapshot Recovery for Remote Jobs
<!-- SID:impl.snapshot_recovery.overview -->

## 概述

快照恢复功能允许系统在中断后恢复执行，特别是支持远程作业的断点续传。当远程作业（如 ESMFold 结构预测）在执行过程中被中断时，系统可以从快照中恢复作业状态并继续执行，而无需重新提交作业。

## 功能特性

- **自动快照写入**：在远程作业提交后自动保存快照，包含 job_id、endpoint 等恢复所需信息
- **断点续传**：从快照恢复后可以继续轮询和下载远程作业结果
- **最小可恢复上下文**：快照包含恢复所需的最小信息（state、plan_version、step_index、artifacts）
- **与现有流程集成**：与 `PlanRunner.run_plan(resume_from_existing=True)` 协同工作

## 架构设计

### 核心组件

1. **TaskSnapshot** (`src/models/contracts.py`)
   - 定义快照数据结构
   - 包含 `artifacts` 字段用于存储远程作业上下文

2. **SnapshotStore** (`src/storage/snapshot_store.py`)
   - `append_snapshot()`: 追加写入快照到 JSONL 文件
   - `read_snapshots()`: 读取任务的所有快照
   - `read_latest_snapshot()`: 读取最新快照

3. **Recovery Module** (`src/workflow/recovery.py`)
   - `RemoteJobContext`: 封装远程作业上下文（job_id、endpoint、status 等）
   - `restore_context_from_snapshot()`: 从快照恢复 WorkflowContext
   - `extract_remote_job_context()`: 从快照提取远程作业信息

4. **RemoteESMFoldAdapter** (`src/adapters/remote_esmfold_adapter.py`)
   - 支持在执行期间写入快照
   - 支持通过 `resume_job_id` 参数恢复作业

### 快照结构
<!-- SID:impl.snapshot_recovery.snapshot_schema -->

快照使用 JSONL 格式存储在 `data/snapshots/{task_id}.jsonl`。每个快照包含：

```json
{
  "snapshot_id": "snapshot_abc123",
  "task_id": "task_001",
  "state": "RUNNING",
  "plan_version": 1,
  "step_index": 2,
  "current_step_index": 2,
  "completed_step_ids": ["S1", "S2"],
  "artifacts": {
    "remote_jobs": {
      "S2": {
        "job_id": "esmfold_job_xyz789",
        "endpoint": "http://esmfold-server.example.com",
        "step_id": "S2",
        "status": "running",
        "submitted_at": "2026-01-11T10:00:00+00:00",
        "metadata": {}
      }
    }
  },
  "pending_action_id": null,
  "created_at": "2026-01-11T10:05:00+00:00"
}
```

## 使用指南

### 1. 启用快照写入

在创建 `RemoteESMFoldAdapter` 时启用快照写入：

```python
from src.adapters.remote_esmfold_adapter import RemoteESMFoldAdapter
from src.workflow.snapshots import default_snapshot_writer

adapter = RemoteESMFoldAdapter(
    base_url="http://esmfold-server.example.com",
    snapshot_writer=default_snapshot_writer,
    enable_snapshot=True,
)
```

### 2. 正常执行（自动写入快照）

```python
from src.models.contracts import PlanStep
from src.workflow.context import WorkflowContext

# 创建步骤和上下文
step = PlanStep(id="S1", tool="esmfold", inputs={"sequence": "ACDEFGHIKLMNPQRSTVWY"})
context = WorkflowContext(task=task, plan=plan)

# 解析输入（保存 context 引用）
inputs = adapter.resolve_inputs(step, context)

# 执行（自动在提交作业后写入快照）
outputs, metrics = adapter.run_local(inputs)
```

快照会在作业提交后自动写入，包含 job_id 和 endpoint 信息。

### 3. 从快照恢复

如果执行被中断，可以从快照恢复：

```python
from src.storage.snapshot_store import read_latest_snapshot
from src.workflow.recovery import extract_remote_job_context

# 读取最新快照
snapshot = read_latest_snapshot(task_id)
if snapshot is None:
    raise ValueError(f"No snapshot found for task {task_id}")

# 提取远程作业上下文
remote_job_ctx = extract_remote_job_context(snapshot, step_id="S1")
if remote_job_ctx is None:
    raise ValueError(f"No remote job found for step S1")

# 创建新的适配器实例（可以禁用快照写入）
new_adapter = RemoteESMFoldAdapter(
    base_url=remote_job_ctx.endpoint,
    enable_snapshot=False,
)

# 使用恢复的 job_id 继续执行
outputs, metrics = new_adapter.run_remote(
    inputs=inputs,
    resume_job_id=remote_job_ctx.job_id,
)

# 检查是否是恢复的执行
if metrics.get("resumed"):
    print(f"Resumed job {remote_job_ctx.job_id}")
```

### 4. 与 PlanRunner 集成

在更高层次，可以结合 `PlanRunner.run_plan(resume_from_existing=True)` 使用：

```python
from src.workflow.plan_runner import PlanRunner
from src.workflow.recovery import restore_context_from_snapshot

# 尝试从快照恢复上下文
context = restore_context_from_snapshot(
    task=task,
    plan=plan,
    task_id=task_id,
)

if context is None:
    # 没有快照，创建新上下文
    context = WorkflowContext(task=task, plan=plan)
    resume_from_existing = False
else:
    # 从快照恢复，启用 resume 模式
    resume_from_existing = True

# 运行计划
runner = PlanRunner()
runner.run_plan(
    plan,
    context,
    resume_from_existing=resume_from_existing,
)
```

## API 参考

### TaskSnapshot

```python
class TaskSnapshot(BaseModel):
    snapshot_id: str              # 快照唯一 ID
    task_id: str                  # 任务 ID
    state: str                    # 外部状态（ExternalStatus）
    plan_version: Optional[int]   # 计划版本号
    step_index: int               # 当前步骤索引
    current_step_index: int       # 当前步骤索引（同步字段）
    completed_step_ids: List[str] # 已完成的步骤 ID 列表
    artifacts: Dict[str, Any]     # 产物和恢复上下文
    pending_action_id: Optional[str]  # 待处理动作 ID
    created_at: str               # 创建时间戳
```

### SnapshotStore 函数

#### append_snapshot

```python
def append_snapshot(
    snapshot: TaskSnapshot,
    *,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> None:
    """追加写入快照到 JSONL 文件"""
```

#### read_snapshots

```python
def read_snapshots(
    task_id: str,
    *,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> List[TaskSnapshot]:
    """读取任务的所有快照（按时间顺序）"""
```

#### read_latest_snapshot

```python
def read_latest_snapshot(
    task_id: str,
    *,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> Optional[TaskSnapshot]:
    """读取任务的最新快照"""
```

### RemoteJobContext

```python
class RemoteJobContext:
    """远程作业上下文"""

    job_id: str          # 远程作业 ID
    endpoint: str        # 远程服务端点 URL
    step_id: str         # 关联的步骤 ID
    status: str          # 作业状态
    submitted_at: Optional[str]  # 提交时间戳
    metadata: Dict[str, Any]     # 额外元数据

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RemoteJobContext:
        """从字典恢复"""
```

### Recovery 函数

#### restore_context_from_snapshot

```python
def restore_context_from_snapshot(
    task: ProteinDesignTask,
    plan: Plan,
    *,
    task_id: Optional[str] = None,
    snapshot: Optional[TaskSnapshot] = None,
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
) -> Optional[WorkflowContext]:
    """从快照恢复 WorkflowContext"""
```

#### extract_remote_job_context

```python
def extract_remote_job_context(
    snapshot: TaskSnapshot,
    step_id: str,
) -> Optional[RemoteJobContext]:
    """从快照的 artifacts 中提取远程作业上下文"""
```

### RemoteESMFoldAdapter 扩展

#### 构造函数新增参数

```python
def __init__(
    self,
    service: Optional[RemoteModelInvocationService] = None,
    *,
    base_url: Optional[str] = None,
    output_dir: Optional[Path] = None,
    snapshot_writer: Optional[SnapshotWriter] = None,  # 新增
    enable_snapshot: bool = True,                       # 新增
) -> None:
```

#### run_remote 新增参数

```python
def run_remote(
    self,
    inputs: Dict[str, Any],
    output_dir: Optional[Path] = None,
    *,
    resume_job_id: Optional[str] = None,  # 新增：用于恢复作业
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
```

返回的 `metrics` 中新增 `resumed: bool` 字段，指示是否是恢复的执行。

## 实现细节

### 快照写入时机

1. **作业提交后**：在 `RemoteESMFoldAdapter.run_remote()` 中，调用 `submit_job()` 后立即写入快照
2. **状态更新时**（可选）：在轮询期间可以选择性更新快照（当前实现未启用）

### 恢复流程
<!-- SID:impl.snapshot_recovery.recovery_flow -->

1. 读取最新快照
2. 从 `artifacts["remote_jobs"][step_id]` 提取 `RemoteJobContext`
3. 使用 `resume_job_id` 参数调用 `run_remote()`
4. 跳过作业提交，直接进入轮询/下载阶段

### 兼容性

- **向后兼容**：`snapshot_writer` 和 `resume_job_id` 都是可选参数，不影响现有代码
- **渐进式采用**：可以选择性地为特定适配器启用快照功能
- **测试覆盖**：包含单元测试和集成测试

## 限制和注意事项

1. **不恢复 StepResult**：快照不保存完整的 `StepResult` 对象，只保存 `completed_step_ids`
2. **远程服务依赖**：恢复依赖于远程服务仍然可访问且作业仍然存在
3. **手动集成**：目前需要手动在上层代码中集成快照恢复逻辑
4. **单次快照**：当前实现在作业提交时写入一次快照，轮询期间不更新

## 未来改进

1. **自动恢复**：在 `PlanRunner` 或 `StepRunner` 层自动检测和恢复
2. **轮询期间更新快照**：定期更新作业状态到快照
3. **多远程服务支持**：扩展到其他远程工具适配器
4. **快照清理策略**：定期清理旧快照
5. **快照压缩**：对大型 artifacts 进行压缩存储

## 测试

### 单元测试

运行快照相关的单元测试：

```bash
pytest tests/unit/test_task_snapshot.py -v
```

### 集成测试

运行快照恢复的集成测试：

```bash
pytest tests/integration/test_snapshot_recovery.py -v
```

## 相关文件

- `src/models/contracts.py` - TaskSnapshot 定义
- `src/storage/snapshot_store.py` - 快照存储 API
- `src/workflow/recovery.py` - 恢复逻辑
- `src/workflow/snapshots.py` - 快照构建工具
- `src/adapters/remote_esmfold_adapter.py` - ESMFold 远程适配器
- `tests/unit/test_task_snapshot.py` - 单元测试
- `tests/integration/test_snapshot_recovery.py` - 集成测试

## 问题排查

### 快照未写入

- 检查 `enable_snapshot=True`
- 检查 `snapshot_writer` 不为 `None`
- 检查 `data/snapshots/` 目录权限

### 恢复失败

- 检查快照文件是否存在：`ls data/snapshots/{task_id}.jsonl`
- 检查快照中是否包含远程作业信息：`artifacts.remote_jobs`
- 检查远程服务是否仍然可访问
- 检查 job_id 是否仍然有效

### 作业被重新提交而非恢复

- 检查是否传递了 `resume_job_id` 参数
- 检查 `resume_job_id` 是否正确从快照中提取

---

**版本**: 1.0
**更新日期**: 2026-01-11
**对应 Issue**: #77
