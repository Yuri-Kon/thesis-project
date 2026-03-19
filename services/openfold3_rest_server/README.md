# OpenFold3 REST Server

`services/openfold3_rest_server/` 提供远程 OpenFold3 推理服务（FastAPI），用于本地工作流通过 REST 调用 OpenFold3（远程 GPU 服务器部署）。

## 目录

- `services/openfold3_rest_server/app.py`: 服务入口
- `services/openfold3_rest_server/schemas.py`: 请求/响应 schema
- `services/openfold3_rest_server/jobs.py`: 作业状态与落盘管理
- `services/openfold3_rest_server/openfold3_runner.py`: OpenFold3 推理执行器（命令行封装）

## REST Contract

1. `POST /predict`
- request:
```json
{
  "task_id": "task_001",
  "step_id": "S2",
  "inputs": {
    "sequence": "ACDEFGHIKLMNPQRSTVWY",
    "request_id": "req_001",
    "output_format": "pdb"
  }
}
```
- response:
```json
{"job_id":"openfold3_xxx"}
```

2. `GET /job/{job_id}`
- response:
```json
{"job_id":"openfold3_xxx","status":"pending|running|completed|failed|unknown"}
```

3. `GET /results/{job_id}`
- response:
```json
{
  "job_id": "openfold3_xxx",
  "outputs": {
    "pdb_path": "prediction.pdb",
    "plddt": 78.4,
    "artifacts": {
      "summary_path": "summary.json"
    }
  },
  "artifacts": [
    {
      "name": "prediction.pdb",
      "url": "http://host/files/openfold3_xxx/prediction.pdb",
      "type": "file"
    }
  ]
}
```

## Runtime Prerequisites (remote host)

- Conda (Miniconda/Anaconda) + Python 3.12
- 已安装 OpenFold3 推理环境（例如可用 `run_openfold` 命令）
- GPU 驱动与 CUDA 环境（若走真实推理）

示例（conda）：

```bash
conda create -n openfold3-rest python=3.12 -y
conda activate openfold3-rest
pip install fastapi uvicorn pydantic
```

## Environment Variables

- `OPENFOLD3_REST_BASE_DIR`: 作业根目录（默认 `./output/remote/openfold3_jobs`）
- `OPENFOLD3_REST_API_TOKEN`: Bearer token（可选）
- `OPENFOLD3_MODEL_DIR`: 模型目录（默认 `/root/autodl-tmp/models/openfold3`）
- `OPENFOLD3_PREDICT_BIN`: 推理命令（默认 `run_openfold`）
- `OPENFOLD3_PREDICT_CMD`: 自定义完整命令模板（可选）  
  支持占位符：`{query_json}`、`{output_dir}`、`{model_dir}`、`{predict_bin}`
- `OPENFOLD3_EXTRA_ARGS`: 额外命令参数（可选，例如 `--num_recycles=3`）
- `OPENFOLD3_QUERY_FORMAT`: 默认 query 结构（可选，`auto|queries|inputs`，默认 `auto`）
- `OPENFOLD3_DEVICE`: 设备标识（默认 `cuda`）
- `OPENFOLD3_MOCK_MODE`: `1/true` 时启用 mock 推理（用于联调）

### OpenFold3 0.4.0 兼容说明

- `run_openfold predict` 在 0.4.0 通常使用 `--query-json/--output-dir`，并且 `query_json` 顶层为 `queries`。
- 本服务已做自动兼容：
  - 自动识别 `--query-json` vs `--query_json`、`--output-dir` vs `--output_dir`
  - 自动识别 query schema（`queries` / `inputs`）
  - 当仅检测到 `--inference-ckpt-path` 且 `OPENFOLD3_MODEL_DIR` 不存在时，不再强制传该参数（避免默认路径导致立即失败）
- 若你的部署命令与默认封装不一致，仍建议优先使用 `OPENFOLD3_PREDICT_CMD` 显式覆盖。

## Start

```bash
python -m uvicorn services.openfold3_rest_server.app:app --host 0.0.0.0 --port 8200
```

## Quick Check

```bash
curl -X POST http://127.0.0.1:8200/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "task_id":"task_001",
    "step_id":"S2",
    "inputs":{"sequence":"ACDEFGHIKLMNPQRSTVWY","request_id":"req_001"}
  }'
```

## Deployment Notes

- 推荐先在远程机器设置：
```bash
export OPENFOLD3_REST_BASE_DIR=/data/openfold3_jobs
export OPENFOLD3_MODEL_DIR=/data/models/openfold3
export OPENFOLD3_PREDICT_BIN=run_openfold
```
- 若真实命令与默认封装不一致，优先使用 `OPENFOLD3_PREDICT_CMD` 完整覆盖。
- 当你仅做端到端联调时，可以先设置 `OPENFOLD3_MOCK_MODE=1` 验证调用链路，再切换到真实推理。
