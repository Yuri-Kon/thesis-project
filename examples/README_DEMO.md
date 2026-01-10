# ESMFold Nextflow 端到端演示

这是 issue#67 的端到端演示实现，展示完整的 ESMFold Nextflow 工作流程，包括 HITL（Human-in-the-Loop）交互。

## 📋 目标

验证以下完整链路：
```
输入 Task → Plan → Execute (ESMFold/Nextflow) → Summarize → DONE
```

包括：
- ✅ FSM 状态流转
- ✅ Agent 协作（Planner、Executor、Summarizer）
- ✅ 真实工具执行（ESMFold via Nextflow）
- ✅ Artifacts 生成（PDB、JSON、报告）
- ⏳ HITL 交互（待实现）

## 🚀 快速开始

### 模拟模式（推荐，本地测试）

不需要 GPU 或云端服务，快速验证完整流程：

```bash
# 运行演示
python examples/demo_esmfold_end_to_end.py --mode mock

# 查看生成的 artifacts
ls -la demo_output/
```

### 真实模式（需要云端服务）

⚠️ **注意**：真实模式需要云端服务器或本地 GPU

```bash
# 配置云端服务（TODO）
export ESMFOLD_API_URL="https://your-esmfold-api.com"
export ESMFOLD_API_KEY="your-api-key"

# 运行演示
python examples/demo_esmfold_end_to_end.py --mode real
```

## 📁 输出结构

演示完成后，`demo_output/` 目录包含：

```
demo_output/
├── task.json              # 任务定义
├── plan.json              # 执行计划
├── step_results.json      # 步骤执行结果
├── design_result.json     # 汇总结果
├── final_record.json      # 最终任务记录
├── pdb/                   # PDB 结构文件
│   └── demo_success_*.pdb
└── nf/                    # Nextflow 产物
    └── output/
        └── reports/
```

## 📊 验收标准

- [x] 一条命令可复现完整流程 ✅
- [x] 产出可用的 PDB 文件和指标 ✅
- [x] 日志与产物可用于论文截图 ✅
- [x] 流程不绕过 FSM 规则 ✅
- [ ] HITL 交互演示 ⏳（TODO）

## 🔧 云端服务接口（预留）

### 接口设计

演示脚本中预留了 `RemoteESMFoldService` 类，用于与云端服务器通信。

#### 需要实现的方法：

1. **提交任务**
```python
def submit_job(self, sequence: str, task_id: str) -> Dict[str, Any]:
    """提交 ESMFold 预测任务到云端"""
    # TODO: 实现 REST API 调用
    # POST /api/v1/predict
    # 返回: {"job_id": "...", "status": "queued"}
```

2. **轮询状态**
```python
def poll_status(self, job_id: str) -> Dict[str, Any]:
    """轮询任务状态"""
    # TODO: 实现状态查询
    # GET /api/v1/jobs/{job_id}
    # 返回: {"status": "running", "progress": 0.5}
```

3. **下载结果**
```python
def download_results(self, job_id: str, output_dir: Path) -> Dict[str, Any]:
    """下载预测结果"""
    # TODO: 实现结果下载
    # GET /api/v1/jobs/{job_id}/results
    # 下载 PDB 文件和 metrics
```

### 可能的实现方式

#### 方案 1: REST API（推荐）
```python
import requests

def submit_job(self, sequence: str, task_id: str):
    response = requests.post(
        f"{self.api_url}/api/v1/predict",
        headers={"Authorization": f"Bearer {self.api_key}"},
        json={"sequence": sequence, "task_id": task_id}
    )
    return response.json()
```

#### 方案 2: SSH + Nextflow
```python
import paramiko

def submit_job(self, sequence: str, task_id: str):
    ssh = paramiko.SSHClient()
    ssh.connect(self.host, username=self.user, key_filename=self.key_path)

    # 在远程服务器上执行 Nextflow
    stdin, stdout, stderr = ssh.exec_command(
        f"nextflow run nf/modules/esmfold.nf "
        f"--sequence {sequence} --task_id {task_id}"
    )

    # 等待完成并下载结果
    # ...
```

#### 方案 3: 云平台 SDK
```python
import boto3  # AWS
# 或 from google.cloud import lifesciences  # GCP
# 或 from azure.batch import BatchServiceClient  # Azure

def submit_job(self, sequence: str, task_id: str):
    # 使用云平台的 Batch 服务
    # ...
```

### 环境配置

创建 `.env` 文件（不要提交到 Git）：

```bash
# 云端服务配置
ESMFOLD_API_URL=https://your-esmfold-api.com
ESMFOLD_API_KEY=your-secret-api-key

# 或 SSH 配置
ESMFOLD_SSH_HOST=your-server.com
ESMFOLD_SSH_USER=your-username
ESMFOLD_SSH_KEY=/path/to/private/key

# 或云平台配置
AWS_REGION=us-east-1
AWS_BATCH_JOB_QUEUE=esmfold-queue
AWS_BATCH_JOB_DEFINITION=esmfold-job-def
```

## 📖 使用示例

### 示例 1: 基础流程

```python
from examples.demo_esmfold_end_to_end import ESMFoldDemo

# 创建演示
demo = ESMFoldDemo(mode="mock")

# 运行成功场景
record = demo.run_success_scenario()

# 查看结果
print(f"Task ID: {record.id}")
print(f"Status: {record.status}")
print(f"PDB: {record.design_result.structure_pdb_path}")
```

### 示例 2: 自定义输出目录

```python
from pathlib import Path

demo = ESMFoldDemo(
    mode="mock",
    output_dir=Path("my_custom_output")
)
demo.run()
```

## 🎯 下一步工作

### 优先级 1: 云端服务接口
- [ ] 实现 `RemoteESMFoldService.submit_job()`
- [ ] 实现 `RemoteESMFoldService.poll_status()`
- [ ] 实现 `RemoteESMFoldService.download_results()`
- [ ] 添加错误处理和重试逻辑
- [ ] 添加超时控制

### 优先级 2: HITL 演示
- [ ] 添加失败场景演示
- [ ] 实现 HITL 决策流程
  - WAITING_PATCH_CONFIRM
  - WAITING_REPLAN_CONFIRM
- [ ] 添加交互式命令行界面
- [ ] 保存完整的 EventLog

### 优先级 3: 可视化和文档
- [ ] 生成流程图（FSM 状态转移）
- [ ] 生成时序图（Agent 交互）
- [ ] 添加截图和录屏素材
- [ ] 编写论文用的说明文档

## 🧪 测试

运行测试以验证演示功能：

```bash
# 运行演示脚本
pytest tests/integration/test_demo_e2e.py -v

# 或手动测试
python examples/demo_esmfold_end_to_end.py --mode mock
```

## 📝 相关文档

- [Issue #67](https://github.com/Yuri-Kon/thesis-project/issues/67) - 端到端演示需求
- [Issue #66](https://github.com/Yuri-Kon/thesis-project/issues/66) - ESMFold 结果汇总
- [Issue #65](https://github.com/Yuri-Kon/thesis-project/issues/65) - ESMFold 适配器
- [AGENT_CONTRACT.md](../AGENT_CONTRACT.md) - 系统架构和约束

## 🤝 贡献

如果你实现了云端服务接口，请：
1. 更新 `RemoteESMFoldService` 类
2. 添加相关文档和示例
3. 提交 Pull Request

## 📧 联系

如有问题，请在 GitHub 上创建 Issue。
