# 答辩全流程本地静态演示方案

更新时间：2026-05-16

目标日期：2026-05-20 答辩

适用仓库：`/home/yurikon/Documents/thesis/thesis-project.dev`

## 1. 结论

建议实现一个 **本地确定性 Demo Fixture**，用于 5 分钟答辩演示。

该方案不是纯静态 HTML，也不调用远程模型服务。它在本机启动现有 FastAPI + React 工作台，由一个 demo endpoint 或脚本一次性注入固定任务、固定候选、固定事件日志、固定 PDB 与固定报告数据。前端仍走真实 API 路由和真实组件渲染，因此展示效果接近真实系统，但耗时和不稳定性都可控。

推荐实现入口：

```text
POST /demo/defense-full-flow
```

推荐演示 URL：

```text
http://127.0.0.1:8000/ui/task-builder
http://127.0.0.1:8000/ui/tasks/demo_defense_hitl
http://127.0.0.1:8000/ui/tasks/demo_defense_done
http://127.0.0.1:8000/ui/tasks/demo_defense_done/events
```

## 2. 设计依据与边界

本方案依据 `AGENT_CONTRACT.md` 与 doc-slicer 检索到的设计片段：

- `fsm.lifecycle.overview`
- `fsm.states.definitions`
- `fsm.transitions.overview`
- `arch.contracts.pending_action`
- `arch.contracts.decision`
- `arch.contracts.task_snapshot`
- `executor.hitl.responsibilities`
- `executor.hitl.patch_confirm`
- `agent.contracts.plan`
- `agent.contracts.step_result`
- `agent.contracts.design_result`
- `impl.runtime_state.persistence`

必须遵守的边界：

1. 不新增、不重命名、不重新解释 FSM 状态。
2. 不让系统自动替代人类批准 `WAITING_*` 决策。
3. 不把 demo fixture 伪装成真实 LLM 或真实远程结构预测结果。
4. `WAITING_PATCH_CONFIRM` 任务必须保留 pending action，不应在 seed 后自动推进。
5. `DONE` 任务可以是“回放后的最终状态”，但 metadata 必须明确标记 `source=defense_demo_fixture`。
6. PDB、报告、事件日志是演示产物，不代表真实模型推理性能。

## 3. 演示目标

5 分钟内展示以下能力：

1. 输入解析与结构化任务录入
2. 任务列表与状态扫描
3. HITL 候选比较与人工决策界面
4. FSM 等待态、决策态、完成态
5. 事件时间线与审计回放
6. 报告浏览器与 objective scoring
7. 三维结构查看器：PDB 加载、旋转、缩放、点击原子
8. 工具能力 readiness / degraded 信息
9. CEBRA-WP 的 runtime state、候选评分、成本/风险解释

## 4. 非目标

本演示不做：

1. 不调用真实 LLM provider。
2. 不调用 AutoDL、PLM REST、OpenFold3 REST。
3. 不重新跑 84-run 实验矩阵。
4. 不证明结构预测生物学质量。
5. 不宣称 demo PDB 是模型真实推理结果。
6. 不修改核心 FSM 语义或 recovery 策略。

## 5. 总体架构

```text
Browser React Workbench
        |
        | real HTTP API
        v
FastAPI app
        |
        | seed fixed demo records
        v
In-memory TASK_STORE
        |
        +-- TaskRecord: demo_defense_intake
        +-- TaskRecord: demo_defense_hitl
        +-- TaskRecord: demo_defense_done
        |
        +-- output/demo/defense-full-flow/demo_defense_done.pdb
        +-- output/demo/defense-full-flow/demo_defense_done_report.json
        +-- data/logs/demo_defense_*.jsonl
```

该设计复用现有前端页面：

- `TaskBuilderPage`
- `DashboardPage`
- `TaskDetailPage`
- `EventTimelinePage`
- `PendingReviewWorkspace`
- `CandidateComparison`
- `StructureViewerPanel`
- `ReportExplorer`
- `CapabilityReadinessPanel`
- `ModelInvocationPanel`

## 6. Demo 任务设计

### 6.1 `demo_defense_intake`

用途：展示输入解析和结构化任务录入。

建议状态：

```text
DONE 或 CREATED
```

如果只想展示字段，建议用 `DONE`，避免前端显示成未完成错误。metadata 里保留 intake 信息。

建议 goal：

```text
Evaluate a TRP-cage-like peptide sequence under a low-cost structure-first workflow, compare candidate tools, and generate a structure report.
```

建议 constraints：

```json
{
  "task_kind": "sequence_evaluation",
  "objective_type": "stability",
  "sequence": "NLYIQWLKDGGPSSGRPPPS",
  "length_range": [18, 32],
  "budget_policy": "low_cost_first",
  "runtime_policy": "lite_belief_state",
  "requires_human_review": true,
  "prefer_remote": false
}
```

建议 metadata：

```json
{
  "source": "defense_demo_fixture",
  "fixture_role": "input_intake",
  "free_text_input": "请评估一个 TRP-cage-like 短肽序列的稳定性，优先使用低成本结构预测路径，并在高代价步骤前展示候选方案给人工确认。",
  "extracted_fields": {
    "sequence": "NLYIQWLKDGGPSSGRPPPS",
    "objective_type": "stability",
    "budget_policy": "low_cost_first",
    "runtime_policy": "lite_belief_state"
  },
  "confirmed_task_spec": {
    "confirmed_by": "demo_operator",
    "confirmed_at": "<now_iso>"
  }
}
```

展示方式：

- 打开 `Task Builder` 页面，口头说明自然语言输入会被解析为结构化字段。
- 不一定需要现场提交真实表单；可以展示 seeded task 的 metadata 或截图。

### 6.2 `demo_defense_hitl`

用途：展示 HITL 候选比较、默认推荐、风险/成本、工具 readiness、人工决策入口。

建议状态：

```text
ExternalStatus.WAITING_PATCH_CONFIRM
InternalStatus.WAITING_PATCH
```

必须带 `PendingAction(action_type=patch_confirm)`。

建议 Plan：

```json
{
  "task_id": "demo_defense_hitl",
  "steps": [
    {
      "id": "S1",
      "tool": "protgpt2",
      "inputs": {
        "prompt": "TRP-cage-like stable peptide",
        "num_candidates": 3
      }
    },
    {
      "id": "S2",
      "tool": "openfold3_rest",
      "inputs": {
        "sequence_ref": "S1.sequence"
      }
    },
    {
      "id": "S3",
      "tool": "biopython_qc",
      "inputs": {
        "pdb_ref": "S2.pdb_path"
      }
    }
  ],
  "constraints": {
    "budget_policy": "low_cost_first",
    "runtime_policy": "lite_belief_state"
  },
  "metadata": {
    "source": "defense_demo_fixture"
  }
}
```

候选集合建议 3 个：

1. `patch_local_openfold`
   - 默认推荐
   - 本地结构预测替代远程服务
   - risk low, cost low, overall 0.86
2. `patch_remote_retry`
   - 继续远程 OpenFold3 REST
   - risk medium, cost high, overall 0.71
3. `suffix_replan_low_cost`
   - 后缀重规划，改用轻量质量评估路径
   - risk low, cost medium, overall 0.78

建议 PendingAction detail 暴露字段：

```json
{
  "pending_action_id": "pa_demo_defense_patch",
  "task_id": "demo_defense_hitl",
  "action_type": "patch_confirm",
  "status": "pending",
  "default_recommendation": "patch_local_openfold",
  "explanation": "Remote structure service is degraded before a high-cost step; compare patch candidates before resuming execution.",
  "runtime_state_summary": {
    "p_success": 0.64,
    "p_structural_failure": 0.31,
    "recovery_margin": 0.72,
    "expected_remaining_cost": 1.35,
    "evidence_sufficiency": 0.58,
    "budget_pressure": 1.12
  },
  "workflow_action_reason": "Budget pressure and degraded remote readiness make local patch preferable."
}
```

展示方式：

- 打开 `http://127.0.0.1:8000/ui/tasks/demo_defense_hitl`
- 展示候选排序、默认推荐、风险、成本、工具来源、readiness。
- 可以点决策按钮，但答辩中建议不依赖现场提交；预录视频可以展示一次提交。

### 6.3 `demo_defense_done`

用途：展示最终报告、三维结构、事件审计闭环。

建议状态：

```text
ExternalStatus.DONE
InternalStatus.DONE
```

建议 DesignResult：

```json
{
  "task_id": "demo_defense_done",
  "sequence": "NLYIQWLKDGGPSSGRPPPS",
  "structure_pdb_path": "output/demo/defense-full-flow/demo_defense_done.pdb",
  "scores": {
    "plddt_mean": 88.2,
    "stability_proxy": 0.81,
    "sequence_length": 20,
    "qc_pass": true
  },
  "risk_flags": [
    {
      "level": "warn",
      "code": "demo_fixture",
      "message": "This structure is a deterministic demo artifact, not remote model output."
    }
  ],
  "report_path": "output/demo/defense-full-flow/demo_defense_done_report.json",
  "metadata": {
    "source": "defense_demo_fixture",
    "objective_scoring": {
      "objective_score": 0.84,
      "posterior_score": {
        "aggregate_score": 0.84,
        "evidence_status": "sufficient_for_demo"
      },
      "top_k": [
        {
          "candidate_id": "patch_local_openfold",
          "objective_score": 0.86,
          "posterior_score": {
            "evidence_status": "supported"
          }
        },
        {
          "candidate_id": "suffix_replan_low_cost",
          "objective_score": 0.78,
          "posterior_score": {
            "evidence_status": "supported"
          }
        },
        {
          "candidate_id": "patch_remote_retry",
          "objective_score": 0.71,
          "posterior_score": {
            "evidence_status": "degraded_remote_readiness"
          }
        }
      ],
      "warnings": [
        "demo fixture; no remote inference was executed"
      ],
      "evidence_refs": [
        {
          "type": "event_log",
          "path": "data/logs/demo_defense_done.jsonl"
        },
        {
          "type": "pdb",
          "path": "output/demo/defense-full-flow/demo_defense_done.pdb"
        }
      ]
    },
    "structure_similarity": {
      "hit_count": 3,
      "top_hit": {
        "hit_id": "TRP_CAGE_REFERENCE",
        "tm_score": 0.73,
        "rmsd": 2.1
      }
    }
  }
}
```

展示方式：

- 打开 `http://127.0.0.1:8000/ui/tasks/demo_defense_done`
- 展示任务快照、报告浏览器、结构查看器。
- 在结构查看器中旋转、缩放、点击原子。
- 打开 `http://127.0.0.1:8000/ui/tasks/demo_defense_done/events`
- 展示从创建、规划、等待、决策、执行、总结到 DONE 的事件链。

## 7. 事件日志设计

每个 demo task 应写入 `data/logs/{task_id}.jsonl`，使 `EventTimelinePage` 走真实 `/tasks/{id}/events`。

### 7.1 `demo_defense_hitl` 事件

建议事件序列：

```text
1. TASK_CREATED
2. TASK_INTAKE_CONFIRMED
3. STATE_TRANSITION CREATED -> PLANNING
4. PLAN_CANDIDATES_GENERATED
5. STATE_TRANSITION PLANNING -> PLANNED
6. STATE_TRANSITION PLANNED -> RUNNING
7. STEP_FINISHED S1
8. TOOL_READINESS_DEGRADED openfold3_rest
9. RUNTIME_STATE_UPDATED
10. PENDING_ACTION_CREATED pa_demo_defense_patch
11. WAITING_ENTER WAITING_PATCH_CONFIRM
12. STATE_TRANSITION RUNNING -> WAITING_PATCH_CONFIRM
```

注意：该任务应该停在等待态，不应写 `DECISION_APPLIED`。

### 7.2 `demo_defense_done` 事件

建议事件序列：

```text
1. TASK_CREATED
2. TASK_INTAKE_CONFIRMED
3. STATE_TRANSITION CREATED -> PLANNING
4. PLAN_CANDIDATES_GENERATED
5. STATE_TRANSITION PLANNING -> PLANNED
6. STATE_TRANSITION PLANNED -> RUNNING
7. STEP_FINISHED S1
8. TOOL_READINESS_DEGRADED openfold3_rest
9. RUNTIME_STATE_UPDATED
10. PENDING_ACTION_CREATED pa_demo_defense_patch
11. WAITING_ENTER WAITING_PATCH_CONFIRM
12. DECISION_SUBMITTED accept patch_local_openfold
13. DECISION_APPLIED
14. WAITING_EXIT
15. STATE_TRANSITION WAITING_PATCH_CONFIRM -> RUNNING
16. STEP_FINISHED S2
17. STEP_FINISHED S3
18. STATE_TRANSITION RUNNING -> SUMMARIZING
19. SUMMARY_CREATED
20. STATE_TRANSITION SUMMARIZING -> DONE
```

事件 data 中建议包含：

- `from_status`
- `to_status`
- `step_id`
- `tool`
- `pending_action_id`
- `decision`
- `runtime_state_summary`
- `artifact_paths`

## 8. PDB 与报告产物

推荐路径：

```text
output/demo/defense-full-flow/demo_defense_done.pdb
output/demo/defense-full-flow/demo_defense_done_report.json
output/demo/defense-full-flow/demo_defense_manifest.json
```

PDB 可以复用现有 `_demo_structure_pdb_text()` 的合成结构，也可以稍作扩展为 50 到 80 个残基的 helix bundle。优先使用合成结构，因为：

- 可控
- 文件小
- 不依赖外部工具
- 足够展示结构查看器交互

报告 JSON 内容应与 `DesignResult.metadata` 保持一致，避免前端显示字段互相矛盾。

## 9. API 设计

### 9.1 启用开关

沿用现有环境变量：

```text
PROTEIN_ENABLE_DEMO_FIXTURES=1
```

如果未启用，demo endpoint 返回 404：

```json
{
  "detail": "demo fixtures are disabled"
}
```

### 9.2 Endpoint

```text
POST /demo/defense-full-flow
```

响应：

```json
{
  "tasks": {
    "intake": "demo_defense_intake",
    "hitl": "demo_defense_hitl",
    "done": "demo_defense_done"
  },
  "urls": {
    "dashboard": "/ui",
    "task_builder": "/ui/task-builder",
    "hitl_task": "/ui/tasks/demo_defense_hitl",
    "done_task": "/ui/tasks/demo_defense_done",
    "done_events": "/ui/tasks/demo_defense_done/events",
    "structure": "/tasks/demo_defense_done/structure"
  },
  "artifacts": {
    "pdb": "output/demo/defense-full-flow/demo_defense_done.pdb",
    "report": "output/demo/defense-full-flow/demo_defense_done_report.json",
    "manifest": "output/demo/defense-full-flow/demo_defense_manifest.json"
  }
}
```

### 9.3 可选脚本

也可以提供脚本：

```text
scripts/seed_defense_full_flow_demo.py
```

但由于 `TASK_STORE` 是进程内内存，单独脚本很难修改正在运行的 API 进程。除非脚本通过 HTTP 调用 endpoint，否则 endpoint 是主入口。

## 10. 后端实现位置

最小改动可以放在：

```text
src/api/main.py
```

但为了避免 `main.py` 继续膨胀，推荐新增：

```text
src/api/demo_fixtures.py
```

职责：

```text
build_defense_full_flow_demo(now: Callable[[], str]) -> DefenseDemoBundle
write_defense_demo_artifacts(bundle: DefenseDemoBundle) -> None
seed_defense_demo_task_store(task_store: dict[str, TaskRecord], bundle: DefenseDemoBundle) -> None
write_defense_demo_event_logs(bundle: DefenseDemoBundle, log_dir: Path) -> None
```

`src/api/main.py` 只保留 endpoint：

```python
@app.post("/demo/defense-full-flow")
async def create_defense_full_flow_demo() -> dict[str, object]:
    if os.getenv("PROTEIN_ENABLE_DEMO_FIXTURES") != "1":
        raise HTTPException(status_code=404, detail="demo fixtures are disabled")
    return seed_defense_full_flow_demo(TASK_STORE)
```

## 11. 前端改动

理论上最小实现不需要改前端。

如果时间允许，可以加一个小入口：

- Dashboard 顶部在 demo fixture 启用时显示“答辩演示任务”按钮
- 点击后调用 `/demo/defense-full-flow` 并跳转到 `demo_defense_hitl`

但 5 月 20 日前优先保证稳定，不建议新增复杂前端交互。用 curl seed 后直接打开固定 URL 更稳。

## 12. 运行命令

启动服务：

```bash
PROTEIN_ENABLE_DEMO_FIXTURES=1 \
UV_CACHE_DIR=/tmp/uv-cache \
uv run python scripts/run_demo.py --port 8000 --no-smoke-test
```

注入演示数据：

```bash
curl -X POST http://127.0.0.1:8000/demo/defense-full-flow
```

打开页面：

```text
http://127.0.0.1:8000/ui
http://127.0.0.1:8000/ui/task-builder
http://127.0.0.1:8000/ui/tasks/demo_defense_hitl
http://127.0.0.1:8000/ui/tasks/demo_defense_done
http://127.0.0.1:8000/ui/tasks/demo_defense_done/events
```

## 13. 5 分钟演示脚本

### 0:00 - 0:30 系统定位

讲法：

```text
这是一个面向蛋白质设计任务的 LLM 多智能体工作流系统。它不是只调用一次模型，而是用显式 FSM 管理任务生命周期，在高代价步骤前进行候选比较、人工确认、恢复和审计记录。
```

页面：

```text
/ui
```

### 0:30 - 1:10 输入解析与任务录入

页面：

```text
/ui/task-builder
```

讲法：

```text
系统入口支持自然语言任务描述，并收敛到结构化任务字段，例如 sequence、objective、budget policy、runtime policy。答辩演示使用本地 fixture，避免现场调用远程模型。
```

### 1:10 - 2:20 HITL 候选对比

页面：

```text
/ui/tasks/demo_defense_hitl
```

讲法：

```text
任务执行到高代价结构预测前，远程工具 readiness 变为 degraded，系统暂停在 WAITING_PATCH_CONFIRM。这里展示的是 PendingAction：三个候选方案按评分、风险、成本和工具可用性排序，默认推荐是本地 patch。
```

重点展示：

- 外部状态：`WAITING_PATCH_CONFIRM`
- 候选数量
- 默认推荐
- score breakdown
- risk/cost
- readiness degraded reason
- runtime state summary

### 2:20 - 3:30 完成态、报告与结构查看器

页面：

```text
/ui/tasks/demo_defense_done
```

讲法：

```text
这是同一类任务在人工接受 patch 后的完成态回放。系统生成 DesignResult，包括序列、结构文件、评分、风险标记和报告路径。右侧结构查看器直接加载 PDB，可以旋转、缩放并点击原子。
```

重点展示：

- `DONE`
- `DesignResult`
- `ReportExplorer`
- objective scoring top-k
- structure similarity
- 3D 结构交互

### 3:30 - 4:30 事件时间线与审计

页面：

```text
/ui/tasks/demo_defense_done/events
```

讲法：

```text
每个状态变化和关键动作都会写入 EventLog。这里可以看到从任务创建、规划、进入等待态、提交决策、应用决策、退出等待态，到执行完成和总结的完整链路。这说明 HITL 不是旁路按钮，而是 FSM 的一部分。
```

重点展示：

- `WAITING_ENTER`
- `DECISION_SUBMITTED`
- `DECISION_APPLIED`
- `WAITING_EXIT`
- `STEP_FINISHED`
- `SUMMARY_CREATED`
- `DONE`

### 4:30 - 5:00 实验结果收束

页面或口头：

```text
docs/experiment/thesis-final-v1-results.md
```

讲法：

```text
真实实验矩阵已离线完成，包含 12 个任务、4 组策略、84 次运行，81 次完成。答辩现场展示的是可复现的本地演示，真实结果用于证明系统和 CEBRA-WP 机制已在更大任务集上运行过。
```

## 14. 测试计划

### 14.1 单元测试

新增：

```text
tests/api/test_defense_demo_fixture.py
```

覆盖：

1. 未启用 `PROTEIN_ENABLE_DEMO_FIXTURES` 时 endpoint 返回 404。
2. 启用后 endpoint 返回三个 task id 和 URL。
3. `/tasks/demo_defense_hitl` 返回 `WAITING_PATCH_CONFIRM`。
4. `demo_defense_hitl.pending_action.action_type == patch_confirm`。
5. `/tasks/demo_defense_done/report` 返回 objective scoring。
6. `/tasks/demo_defense_done/structure` 返回 PDB 文本。
7. `/tasks/demo_defense_done/events` 包含 `WAITING_ENTER`、`DECISION_APPLIED`、`WAITING_EXIT`、`DONE`。

### 14.2 前端 smoke

如果已有前端 smoke 基础，补充：

```text
GET /ui/tasks/demo_defense_hitl
GET /ui/tasks/demo_defense_done
GET /ui/tasks/demo_defense_done/events
```

并确认 HTML shell 返回 200。

### 14.3 手工验收

验收清单：

- Dashboard 能看到 seeded tasks 或能通过 TaskSearch 打开。
- HITL 页面候选卡片不空。
- 决策区域不报错。
- DONE 页面报告浏览器有评分表。
- 结构查看器不是空白 canvas。
- 结构查看器可以旋转、缩放。
- 时间线至少 15 条事件。
- 全程不访问远程 REST。

## 15. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| `TASK_STORE` 是内存态，重启后丢失 | 页面 404 | 启动后固定执行 seed endpoint |
| endpoint 忘记启用环境变量 | seed 404 | 启动脚本显式设置 `PROTEIN_ENABLE_DEMO_FIXTURES=1` |
| 事件日志格式与 timeline parser 不兼容 | 时间线为空 | 复用现有 log_store 写入函数，不手写不兼容 JSON |
| PDB 太小或坐标不佳 | 结构显示不明显 | 复用并扩展现有 `_demo_structure_pdb_text()` |
| 前端 build 不是最新 | 页面不含新 UI 修复 | 实现后运行 `npm run build:ui` 或使用现有静态构建 |
| 答辩现场命令失败 | 影响演示 | 预录视频为主，现场只做备份 |

## 16. 实现顺序

建议按以下顺序实现：

1. 新增 `src/api/demo_fixtures.py`，只构建数据，不接路由。
2. 在 `src/api/main.py` 增加 `/demo/defense-full-flow` endpoint。
3. 生成 PDB、report、manifest 三类产物。
4. 写入 `data/logs/demo_defense_*.jsonl`。
5. 补 API 测试。
6. 本地启动服务手工检查四个页面。
7. 录制 5 分钟视频。

## 17. 对论文/答辩的表述边界

推荐说法：

```text
为了避免答辩现场远程服务耗时和不稳定，本演示使用本地确定性 fixture 展示系统交互和证据链。真实实验矩阵已离线完成，演示只用于说明前端、FSM、HITL、结构查看和审计功能如何联动。
```

避免说法：

```text
这个演示现场完成了真实蛋白结构预测。
这个 PDB 是 OpenFold3 实时推理结果。
算法显著提升了最终成功率。
```

更稳的结论：

```text
系统具备从任务输入、候选生成、人工确认、恢复控制、结果汇总、结构展示到事件审计的完整工程闭环。CEBRA-WP 的主要价值体现在运行时可观测、恢复决策和高代价流程控制，而不是简单声称最终成功率提升。
```

## 18. 后续可扩展项

答辩后可继续扩展：

1. 把 fixture 改成从 `output/experiment/thesis-final-matrix/...` 选择真实 run 生成。
2. 增加视频录制脚本或 Playwright 自动截图。
3. 在 Dashboard 增加 demo launcher。
4. 增加一个真实远程服务模式开关，用于实验室环境而非答辩现场。
5. 将 demo manifest 纳入论文附录证据索引。
