# 可用性补充验证报告

- 生成时间：`2026-03-20T14:30:00+08:00`
- 基线提交：`95c54ff`
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
- `OpenFold3 REST` 当前仍按 `OPENFOLD3_MOCK_MODE=1` 运行

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
- 本轮还通过本地仓库经 SSH 转发直连 `OpenFold3 REST`，验证了适配器侧的真实调用链，而不仅是服务端自测。

### 2.3 PLM REST 验证结果

验证链路：

- `POST /predict`
- `GET /job/{job_id}`

结果：

- 服务成功接收任务并返回 `job_id`
- 轮询状态从 `running` 进入 `completed`
- `GET /results/{job_id}` 成功返回：
  - 有效 `sequence`
  - `candidates`
  - `candidates.fasta`
  - `summary.json`

结论：

- 你在 AutoDL 上补齐 `transformers` 之后，`PLM REST` 已经可以完成真实推理。
- 先前阻塞 `ProtGPT2` 远程 REST 可用性的核心问题已经解除。
- 本轮未再复现早先的 `status.json` 读取竞态导致的 `500`，但该问题是否彻底消失，还需要更高频轮询压测后才能下结论。

### 2.4 本地仓库直连远程 REST 的真实闭环

为补齐“本地 `thesis-project.dev` 直接调用远程 REST 工具”的最后一跳，本轮通过 SSH 本地端口转发建立：

- `127.0.0.1:38100 -> AutoDL:8100`
- `127.0.0.1:38200 -> AutoDL:8200`

随后使用本地仓库真实适配器和执行器完成了两类验证：

1. 真实双工具链：
   - `ProtGPT2Adapter(base_url=http://127.0.0.1:38100)`
   - `OpenFold3Adapter(execution_mode=openfold3_rest, base_url=http://127.0.0.1:38200)`
   - 结果：`DONE -> DONE`
   - `S1` 返回真实远程序列，`S2` 返回真实远程结构结果与 `pdb_path`

2. 真实三阶段链：
   - `S1: protgpt2`
   - `S2: openfold3_rest`
   - `S3: biopython_qc`
   - `SummarizerAgent`
   - 结果：`DONE -> DONE`
   - `quality_gate.status = PASS`

这说明此前“本机到远端服务联通方式不稳定”的问题，在本轮已经通过 SSH 转发方案被实测打通。

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

### 链路 E：真实远程 REST 工具的本地完整执行链

- 入口：本地 `ExecutorAgent + SummarizerAgent`
- 计划：
  - `S1: protgpt2`
  - `S2: openfold3_rest`
  - `S3: biopython_qc`
- 结果：
  - 三个步骤全部成功
  - `S1.provider = plm_rest`
  - `S2.provider = openfold3_rest`
  - `S3.quality_gate.status = PASS`
  - 任务到达 `DONE`
- 证据：
  - 新增集成测试 [test_plm_remote_e2e.py](/home/yurikon/文档/thesis/thesis-project.dev/tests/integration/test_plm_remote_e2e.py)
  - 新增集成测试 [test_remote_rest_full_e2e.py](/home/yurikon/文档/thesis/thesis-project.dev/tests/integration/test_remote_rest_full_e2e.py)
  - 验证命令：

```bash
UV_CACHE_DIR=.uv-cache \
PLM_E2E_BASE_URL=http://127.0.0.1:38100 \
OPENFOLD3_E2E_BASE_URL=http://127.0.0.1:38200 \
uv run pytest \
  tests/integration/test_plm_remote_e2e.py \
  tests/integration/test_openfold3_remote_e2e.py \
  tests/integration/test_remote_rest_full_e2e.py \
  -q --durations=20
```

结果：

- `5 passed, 1 warning in 39.25s`
- 主要耗时热点：
  1. `test_plm_rest_service_submit_poll_download_e2e`：`13.55s`
  2. `test_remote_rest_full_flow_e2e`：`12.04s`
  3. `test_executor_protgpt2_rest_e2e`：`11.82s`
  4. `test_openfold3_rest_service_submit_poll_download_e2e`：`0.78s`
  5. `test_executor_openfold3_rest_e2e`：`0.48s`

### 链路 F：API 入口到终态

- 入口：`POST /tasks`
- 方式：本地 ASGI 客户端调用 API，同步执行 `run_task_sync`
- 结果：
  - `status = DONE`
  - `internal_status = DONE`
  - 成功返回完整 `TaskRecord`
  - 事件链完整写入

补充说明：

- 该 API 入口链路本轮确认为可用，但默认 planner 仍优先选择 `protgpt2 -> esmfold -> protein_mpnn -> esmfold` 路径，而不是 `openfold3_rest`。
- 这不是远程 REST 不可用，而是当前 planner 的默认候选排序更偏向本地 `esmfold`。

## 5. 当前真实可用性结论

### 已确认可用

- 初始 planning 的真实 provider 调用
- `patch / replan` 的真实 provider 调用（`qwen-plus` / `deepseek-chat` / `glm-5`）
- API 端点级功能
- 本地完整工作流闭环
- `PLM REST` 的真实推理调用
- `OpenFold3 REST` 的服务契约（mock 模式）
- 本地仓库经 SSH 转发直连远程 REST 的真实双工具链与三阶段闭环

### 已确认存在问题

- `OpenFold3 REST` 当前仍是 mock 模式，尚未验证真实模型推理
- Planner 默认排序对 `openfold3_rest` 不友好，API 默认链路不会自然优先选到它
- `PLM REST` 历史上存在状态文件写入/读取竞态风险，但本轮未复现，需要单独压测确认

## 6. 后续建议

1. 如果要把 `OpenFold3 REST` 也提升为“真实模型可用”，下一步需要在 AutoDL 上补齐其模型目录并关闭 mock 模式重测。
2. 若希望 API 默认链路自然覆盖远程结构工具，应在不改变 FSM/职责边界的前提下，重新评估 planner 对 `openfold` 的排序策略。
3. 建议单独做一次高频轮询压测，确认 `PLM REST` 的状态文件竞态是否已经被环境变化间接缓解，或是否仍需服务端修复。
