# 可用性补充验证报告

- 生成时间：`2026-03-20T00:17:34+08:00`
- 基线提交：`b1adda6`
- 目标：补充验证以下四类能力：
  1. Planner 的 `patch / replan` 在真实 LLM 下是否可用
  2. 根据 `AGENTS.md` 启用远程服务后，REST 工具依赖的服务是否真实可用
  3. API 端点级别验证
  4. 从可用性视角再次确认全流程覆盖，并确认若干完整执行链

## 1. Planner Recovery 的真实 LLM 验证

本轮采用真实 provider 直接调用 `call_patch` / `call_replan`，验证返回结果是否能形成可用的 `PlanPatch` / `Plan`。

结果文件：

- [llm_recovery_smoke_report.json](/home/yurikon/文档/thesis/thesis-project.dev/reports/llm_recovery_smoke_report.json)

结果：

| Provider | Patch | Replan | 结论 |
|---|---|---|---|
| `qwen-plus` | `replace_step -> esmfold` | `protgpt2 -> esmfold -> biopython_qc` | 成功 |
| `deepseek-chat` | `replace_step -> esmfold` | `protgpt2 -> esmfold -> biopython_qc` | 成功 |
| `glm-5` | `replace_step -> esmfold` | `protgpt2 -> esmfold -> biopython_qc` | 成功 |

结论：

- 真实 LLM 不仅能生成初始 plan，也能对失败上下文返回结构化、可执行的 recovery 结果。
- 本轮 recovery 结果在三个 provider 上收敛到同一恢复策略：
  - Patch：将失败的 `nim_esmfold` 替换为 `esmfold`
  - Replan：保留 `protgpt2 -> 结构预测 -> biopython_qc` 的三步链，只把结构预测从远端候选切到本地 `esmfold`

补充说明：

- `nemotron` 本轮未纳入最终 recovery 报告，因为 direct recovery 收口明显更慢，未在当前窗口内作为主结论采用。
- 先前 `scripts/smoke_test_llm_recovery.py` 在本环境中表现不稳定，但 direct provider 调用已验证 provider 能力本身可用。

## 2. 远程 REST 服务验证

### 2.1 启动方式

按 `AGENTS.md` 与 `../remote-server/README.md` 的约束，在 AutoDL 上使用：

- `ssh autodl`
- `conda activate plm`
- `cd /root/projects/2022112879/remote-model-rest`

实际启动结果：

- `PLM REST` 已监听 `0.0.0.0:8100`
- `OpenFold3 REST` 已监听 `0.0.0.0:8200`

其中：

- `PLM REST` 使用真实模型目录 `/root/autodl-tmp/models/plm/ProtGPT2`
- `OpenFold3 REST` 因模型目录缺失，本轮按文档使用 `OPENFOLD3_MOCK_MODE=1`

### 2.2 OpenFold3 REST 验证结果

验证链路：

- `POST /predict`
- `GET /job/{job_id}`
- `GET /results/{job_id}`

结果：

- 成功返回 `job_id`
- 作业状态为 `completed`
- 成功返回：
  - `prediction.pdb`
  - `summary.json`
  - `plddt = 75.0`

结论：

- `OpenFold3 REST` 的服务契约在 mock 模式下是可用的，REST 调用链闭环成立。

### 2.3 PLM REST 验证结果

验证链路：

- `POST /predict`
- `GET /job/{job_id}`

结果：

- 服务可以成功接收任务并返回 `job_id`
- 随后状态轮询返回：
  - `status = failed`
  - `failure.message = "No module named 'transformers'"`

同时，远端日志还暴露出另一个问题：

- 在过早轮询 `GET /job/{job_id}` 时，服务端可能读取到未写完的状态文件并抛出 JSON 解析错误，表现为 `500`

结论：

- `PLM REST` 的网络与 HTTP 契约是通的，但其当前远端运行环境不完整，缺少 `transformers`
- 此外服务端存在状态文件读取竞态，早轮询可能触发 `500`
- 因此，本轮不能将 `ProtGPT2` 远程 REST 工具判定为“真实可用”

## 3. API 端点级验证

执行命令：

```bash
uv run pytest tests/api/test_api_endpoints.py -q --durations=20
```

结果：

- `30 passed, 3 warnings in 39.15s`

说明：

- 为保证 API 端点测试验证的是 API 契约与本地工作流，而非外部 provider 的偶发输出，本轮对 `tests/api/test_api_endpoints.py` 增加了和 planner 测试一致的环境隔离：
  - `PLANNER_LLM_PROVIDER=off`
  - 清理外部 LLM API key

这个改动是测试隔离，不改变产品运行逻辑。

主要耗时热点：

1. `test_create_task_with_custom_constraints`：`10.12s`
2. `test_create_task_generates_unique_ids`：`9.75s`
3. `test_get_task_endpoint_success`：`4.87s`

结论：

- `/tasks`
- `/tasks/{id}`
- `/pending-actions`
- `/pending-actions/{id}`
- `/pending-actions/{id}/decision`
- `/tasks/{id}/events`
- `/health`
- `/ui` 及静态资源

这些 API 端点在本地确定性模式下全部通过。

## 4. 完整执行链路确认

本轮结合此前已通过的验证，确认以下完整链路成立：

### 链路 A：API 创建任务到终态

- 入口：`POST /tasks`
- 结果：任务被创建、执行并返回完整 `TaskRecord`
- 证据：`tests/api/test_api_endpoints.py::TestAPIEndpoints::test_create_task_endpoint`

### 链路 B：六阶段 HITL 决策回放到 DONE

- 入口：`scripts/run_w12_issue151_demo_audit.py`
- 结果：
  - `audit_chain_pendingaction_decision_eventlog = PASS`
  - `tool_fallback_switch_recorded = PASS`
  - `e2e_flow_reaches_done = PASS`
- 证据：
  - [demo-summary.json](/home/yurikon/文档/thesis/thesis-project.dev/output/demo/w12-issue-151/demo-summary.json)
  - [release-validation.md](/home/yurikon/文档/thesis/thesis-project.dev/output/demo/w12-issue-151/release-validation.md)

### 链路 C：Mock Remote 执行器 + Summarizer 到 DONE

- 入口：`tests/integration/test_mock_remote_full_flow.py`
- 结果：
  - 远程结构预测适配器返回成功
  - `SummarizerAgent` 输出 `DesignResult`
  - 任务状态到达 `DONE`

### 链路 D：真实 LLM 的 Recovery 链

- 入口：direct `call_patch` / `call_replan`
- 结果：
  - 三个真实 provider 均返回可用的恢复结构
  - 返回内容可以组成完整的恢复控制链

## 5. 当前真实可用性结论

### 已确认可用

- 初始 planning 的真实 provider 调用
- `patch / replan` 的真实 provider 调用（`qwen-plus` / `deepseek-chat` / `glm-5`）
- API 端点级功能
- 本地完整工作流闭环
- `OpenFold3 REST` 的服务契约（mock 模式）

### 已确认存在问题

- `PLM REST` 当前远端环境缺少 `transformers`，无法完成真实推理
- `PLM REST` 存在状态文件写入/读取竞态，早轮询可能触发 `500`
- 本执行环境中的 SSH 本地端口转发不稳定，因此本轮对远程 REST 工具的验证主要在服务端侧完成，而非通过本地适配器直接联调

## 6. 后续建议

1. 在 AutoDL 的 `plm` 环境中补齐 `transformers` 依赖，再重做 `ProtGPT2` 远程 REST 验证。
2. 在远程服务仓库中修复状态文件竞态，避免 `GET /job/{id}` 读取到半写入 JSON。
3. 若需要真正完成“本地 thesis-project.dev -> 远程 REST 工具 -> 总结报告”的实链路，下一步应先解决本机 SSH 端口转发或提供可直接访问的服务地址。
