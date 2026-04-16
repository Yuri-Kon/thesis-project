# LLM Provider 验证报告

- 生成时间：`2026-03-19T23:29:09+08:00`
- 修复前基线提交：`d7aa6f9`（`feat(llm): add multi-provider planning support`）

## 验证范围

本报告用于验证本次新增的多 provider 规划能力，以及相关 smoke 验证脚本是否真实可用。

## 已完成修复

- 为 planner 相关测试补上环境隔离，避免真实 shell 中已有 API key 干扰默认路径断言。
- 更新过时的 patch-agent 测试预期，使其与当前分层恢复策略一致：优先参数级修补，再考虑工具级替换。
- 强化 `scripts/smoke_test_llm_providers.py`，补充：
  - provider 级硬超时
  - 子进程隔离
  - 结构化失败采集
  - 进度日志输出
  - 适合后续实验分析的 JSON 报告落盘
- 新增 smoke 脚本的单元测试，覆盖超时和缺少 API key 两种场景。

## 验证命令

```bash
uv run pytest tests/unit/test_provider_registry.py tests/unit/test_anthropic_messages_provider.py tests/unit/test_openai_compatible_provider.py tests/unit/test_planner_agent.py tests/unit/test_protein_tool_kg.py -q --durations=10
uv run pytest tests/unit/test_planner_with_provider.py tests/unit/test_planner_patch_agent.py tests/unit/test_smoke_test_llm_providers.py -q
uv run pytest tests/unit -q --durations=20
UV_CACHE_DIR=.uv-cache uv run python scripts/smoke_test_llm_providers.py --providers qwen-plus,deepseek-chat,glm-5,nemotron --per-provider-timeout 15 --output reports/llm_provider_smoke_report.json
uv run python scripts/run_w12_issue151_demo_audit.py
```

## 结果

### 单元测试

- `tests/unit` 总计：`495 passed`、`0 failed`、`1 warning`
- 总耗时：`20.97s`

`--durations=20` 给出的主要耗时热点如下：

1. `tests/unit/test_plan_runner.py::test_auto_replan_resolves_pending_action`：`6.69s`
2. `tests/unit/test_patch_runner.py::test_patch_runner_triggers_patch_and_records_meta`：`2.05s`
3. `tests/unit/test_visualization_adapter.py::test_invalid_pdb_ref_enters_waiting_replan`：`2.05s`
4. `tests/unit/test_patch_runner.py::test_patch_runner_enters_waiting_patch_when_gate_requires_hitl`：`2.00s`
5. `tests/unit/test_plan_runner.py::test_run_plan_executes_insert_before_patch_steps`：`2.00s`

### 真实 provider smoke

详细结果已写入 [llm_provider_smoke_report.json](/home/yurikon/文档/thesis/thesis-project.dev/reports/llm_provider_smoke_report.json)。

| Provider | 是否成功 | 耗时（秒） | 结果 |
|---|---:|---:|---|
| `qwen-plus` | 是 | 4.680 | 生成 3 步可执行计划 |
| `deepseek-chat` | 是 | 13.503 | 生成 3 步可执行计划 |
| `glm-5` | 是 | 9.347 | 生成 3 步可执行计划 |
| `nemotron` | 是 | 5.258 | 生成 3 步可执行计划 |

四个 provider 返回的步骤序列一致，均为：

`protgpt2 -> nim_esmfold -> biopython_qc`

### 端到端测试

端到端审计脚本 `uv run python scripts/run_w12_issue151_demo_audit.py` 运行成功，退出码为 `0`。

生成摘要位于 [demo-summary.json](/home/yurikon/文档/thesis/thesis-project.dev/output/demo/w12-issue-151/demo-summary.json)，发布验证位于 [release-validation.md](/home/yurikon/文档/thesis/thesis-project.dev/output/demo/w12-issue-151/release-validation.md)。

两条确定性端到端场景均通过：

1. `tests/integration/test_s6_control_layer_e2e.py::test_six_stage_waiting_patch_decision_replay_to_done`
2. `tests/integration/test_recovery_layered_patch.py::test_layered_patch_promotes_remote_to_local_tool_level`

关键门禁结果：

- `audit_chain_pendingaction_decision_eventlog = PASS`
- `tool_fallback_switch_recorded = PASS`
- `e2e_flow_reaches_done = PASS`

## 瓶颈分析

当前主要瓶颈已经从“外部网络不可达”转为“不同 provider 的响应时延差异”。

证据如下：

- 关闭代理后，四个 provider 全部通过真实 smoke，说明先前失败并非由 planner 代码引起。
- 关闭代理后的结果与“代理路径导致出口连通性异常”的推断一致，说明此前 `Connection error` / DNS 解析失败主要来自网络层。
- 当前可观测的性能瓶颈是 provider 响应耗时：
  - `deepseek-chat` 最慢，`13.503s`
  - `glm-5` 次之，`9.347s`
  - `nemotron` 和 `qwen-plus` 相对更快，分别为 `5.258s` 与 `4.680s`
- 四个 provider 都能生成同构的 3 步计划，说明在该 smoke 任务上，计划结构的稳定性较好，差异主要体现在响应延迟而非计划内容。

## 结论

多 provider 规划路径在本地代码层面已经验证通过，且测试干净。
关闭代理后，真实 provider smoke 全部成功，说明系统当前在“真实规划调用”层面已经可用；本地确定性端到端链路也能够完整到达 `DONE`。
