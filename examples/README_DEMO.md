# ESMFold 远程调用 + HITL + 恢复演示

本演示脚本覆盖以下链路：

```
Planner → WAITING_PLAN_CONFIRM → (恢复) → 决策 → Executor(远程 ESMFold) → Summarizer
```

它演示了：
- ✅ Planner 生成计划（支持切换 LLM Provider）
- ✅ 远程 ESMFold 调用（mock/real）
- ✅ HITL 进入 WAITING_PLAN_CONFIRM
- ✅ EventLog + Snapshot 恢复
- ✅ Summarizer 汇总并产出报告

## 快速开始（Mock 模式）

无需 GPU 或远程服务：

```bash
python -m pip install -r requirements.txt
python examples/demo_esmfold_end_to_end.py --mode mock
```

## 真实模式（对接远程 ESMFold 服务）

远程服务需实现 REST API（见 `docs/remote_model_invocation.md`）：

```bash
python examples/demo_esmfold_end_to_end.py \
  --mode real \
  --remote-url http://<host>:<port>
```

或使用环境变量：

```bash
export ESMFOLD_API_URL="http://<host>:<port>"
python examples/demo_esmfold_end_to_end.py --mode real
```

## Planner Provider 切换（可选）

默认使用内置 Planner（`--planner-provider none`）。

示例：使用 Nemotron 规划（需配置 API Key）：

```bash
python examples/demo_esmfold_end_to_end.py \
  --mode mock \
  --planner-provider nemotron
```

Provider 定义在 `configs/llm_providers.json`，你也可以通过 `--provider-config` 指向自定义配置。

## 输出结构

默认输出目录为 `demo_output/`：

```
demo_output/
├── task.json
├── plan.json
├── pending_action.json
├── recovery.json
├── step_results.json
├── design_result.json
└── task_record.json
```

此外，快照与事件日志会写入：

```
data/snapshots/{task_id}.jsonl
data/logs/{task_id}.jsonl
```

`recovery.json` 会记录恢复时的状态对齐与回放信息。

## 远程服务 API 约定

脚本使用 `RemoteESMFoldAdapter + RESTModelInvocationService`，远程服务需满足：

- `POST /predict`
- `GET /job/{job_id}`
- `GET /results/{job_id}`

完整协议详见：`docs/remote_model_invocation.md`

## 相关文档

- `docs/remote_model_invocation.md`
- `docs/snapshot-recovery.md`
