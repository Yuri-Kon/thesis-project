# ProtGPT2 REST Server

`services/plm_rest_server/` 提供远程 ProtGPT2 推理服务（FastAPI），用于本地工作流通过 REST 调用 PLM。

## 目录

- `services/plm_rest_server/app.py`: 服务入口
- `services/plm_rest_server/schemas.py`: 请求/响应 schema
- `services/plm_rest_server/jobs.py`: 作业状态与落盘管理
- `services/plm_rest_server/protgpt2_runner.py`: ProtGPT2 推理实现

## REST Contract

1. `POST /predict`
- request:
```json
{
  "task_id": "task_001",
  "step_id": "S1",
  "inputs": {
    "prompt": "<|endoftext|>",
    "max_new_tokens": 128,
    "num_return_sequences": 4,
    "top_k": 950,
    "top_p": 1.0,
    "temperature": 1.0,
    "repetition_penalty": 1.2,
    "do_sample": true,
    "eos_token_id": 0
  }
}
```
- response:
```json
{"job_id": "plm_xxx"}
```

2. `GET /job/{job_id}`
- response:
```json
{"job_id": "plm_xxx", "status": "pending|running|completed|failed|unknown"}
```

3. `GET /results/{job_id}`
- response:
```json
{
  "job_id": "plm_xxx",
  "outputs": {
    "sequence": "ACDE...",
    "candidates": [{"sequence": "ACDE...", "score": -1.23}],
    "device_used": "cuda",
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

## Runtime Prerequisites (remote host)

- Python 3.12 + uv
- `torch` + `transformers`
- ProtGPT2 model files

## Environment Variables

- `PLM_REST_BASE_DIR`: 作业根目录（默认 `./output/remote/plm_jobs`）
- `PLM_REST_API_TOKEN`: Bearer token（可选）
- `PLM_MODEL_DIR`: ProtGPT2 模型目录（默认 `/root/autodl-tmp/models/plm/ProtGPT2`）

## Start

```bash
uv run uvicorn services.plm_rest_server.app:app --host 0.0.0.0 --port 8100
```

## Quick Check

```bash
curl -X POST http://127.0.0.1:8100/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "task_id":"task_001",
    "step_id":"S1",
    "inputs":{"prompt":"<|endoftext|>","max_new_tokens":32,"num_return_sequences":2}
  }'
```

## Notes

- `num_candidates` 作为 `num_return_sequences` 的兼容别名仍被支持。
