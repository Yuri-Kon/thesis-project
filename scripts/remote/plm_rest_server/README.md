# PLM REST 服务（参考实现）

本目录提供可复用的 PLM 远程调用 REST 协议，以及可直接运行的参考实现。

## 接口端点

1. `POST /predict`
- 请求：
```json
{
  "task_id": "task_001",
  "step_id": "S1",
  "inputs": {
    "goal": "design a soluble binder",
    "length_range": [60, 120],
    "num_candidates": 4,
    "prompt": "MKT..."
  }
}
```
- 响应：
```json
{
  "job_id": "plm_..."
}
```

2. `GET /job/{id}`
- 响应（`pending|running|completed|failed|unknown`）：
```json
{
  "job_id": "plm_...",
  "status": "completed"
}
```
- 失败响应：
```json
{
  "job_id": "plm_...",
  "status": "failed",
  "failure": {
    "code": "REMOTE_JOB_FAILED",
    "message": "...",
    "failure_type": "tool_error",
    "retryable": false
  }
}
```

3. `GET /results/{id}`
- 响应：
```json
{
  "job_id": "plm_...",
  "outputs": {
    "sequence": "ACDE...",
    "candidates": [
      {"sequence": "ACDE...", "score": 0.95}
    ],
    "artifacts": {
      "fasta_path": "candidates.fasta",
      "summary_path": "summary.json"
    }
  },
  "artifacts": [
    {
      "name": "candidates.fasta",
      "url": "http://host/files/plm_xxx/candidates.fasta",
      "type": "file"
    }
  ]
}
```

4. `GET /files/{job_id}/{filename}`
- `artifacts[].url` 对应的产物下载端点。

## 错误响应 Envelope

所有非成功响应统一使用：
```json
{
  "error": {
    "code": "REMOTE_RESULTS_NOT_READY",
    "message": "Job 'plm_xxx' is not completed",
    "retryable": true,
    "details": {}
  }
}
```

## 作业目录约定

每个作业落盘到：
`<remote_base_dir>/<job_id>/`

必需文件：
- `status.json`
- `outputs.json`（completed 时生成）
- `artifacts/`

## 运行方式

示例：
```bash
uv run uvicorn scripts.remote.plm_rest_server.app:app --host 0.0.0.0 --port 8100
```

可选环境变量：
- `PLM_REST_BASE_DIR`（默认：`./output/remote/plm_jobs`）
- `PLM_REST_API_TOKEN`（若设置，请求需携带 `Authorization: Bearer <token>`）

## Runner

`run_plm_job.py` 是当前 issue 范围内的 stub runner。
- 读取标准化输入 payload
- 生成最小输出：`outputs.sequence` 与 `outputs.candidates`
- 写入产物（`candidates.fasta`、`summary.json`）
