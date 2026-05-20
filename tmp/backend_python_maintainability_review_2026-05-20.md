# 后端 Python 代码规模与可维护性审查报告

审查日期：2026-05-20

## 1. 审查范围与工具

范围：

- `src/`
- `services/`
- 仅统计 Python 代码。

工具：

- `cloc 2.08`
- `radon 6.0.1`

执行命令：

```bash
cloc src services --include-lang=Python --by-file
radon cc src services -s -a -n C
radon cc src services -s -a -n D
radon mi src services -s -n C
radon raw src services -s
```

## 2. 总体结论

后端 Python 代码已经具备明显的“工程系统”规模，而不是普通毕业设计原型规模。

`cloc` 统计结果：

| 范围 | Python 文件 | blank | comment | code |
|---|---:|---:|---:|---:|
| `src services` | 104 | 6025 | 2549 | 45294 |

`radon cc -n C` 识别出 185 个复杂度 C 及以上的函数/类/方法，平均复杂度为 `C (18.79)`。

`radon cc -n D` 识别出 42 个复杂度 D/F/E 级热点，热点平均复杂度为 `E (33.74)`。

核心风险不是单纯“代码行数多”，而是：

- 大文件集中：少数模块承担过多职责。
- 高复杂度集中：若干函数达到 E/F 级复杂度。
- 关键路径复杂：`workflow`、`planner`、`task_intake`、`executor` 同时处在系统核心和复杂度热点中。
- 实验/验证代码与核心运行时代码混在 `src/infra` 下，拉高了后端体量叙事。

## 3. 最大文件清单

按 `cloc --by-file` 的 code 行数排序，前 20 个文件：

| 文件 | code | comment | blank | 风险判断 |
|---|---:|---:|---:|---|
| `src/agents/planner.py` | 4711 | 55 | 508 | 极高：单文件过大，职责集中 |
| `src/models/task_intake.py` | 2160 | 45 | 269 | 极高：输入建模、规则抽取、校验混合 |
| `src/api/main.py` | 1737 | 69 | 277 | 高：API 聚合层过重 |
| `src/infra/external_baseline_experiment.py` | 1487 | 2 | 116 | 高：实验脚本复杂 |
| `src/infra/w12_vertical_experiment.py` | 1479 | 2 | 186 | 极高：实验统计函数复杂度异常高 |
| `src/agents/executor.py` | 1422 | 45 | 137 | 高：执行器核心路径较重 |
| `src/infra/thesis_experiment_matrix.py` | 1360 | 35 | 128 | 高：实验矩阵逻辑复杂 |
| `src/cli.py` | 1249 | 1 | 105 | 中高：命令入口承担展示/解析逻辑 |
| `src/models/contracts.py` | 1156 | 102 | 237 | 中：契约层大，但可接受，重构需谨慎 |
| `src/workflow/recovery.py` | 1038 | 66 | 143 | 极高：恢复策略核心且复杂 |
| `src/workflow/plan_runner.py` | 1032 | 114 | 87 | 极高：FSM 执行主路径复杂 |
| `src/models/validation.py` | 979 | 40 | 118 | 高：验证规则集中 |
| `src/workflow/step_runner.py` | 860 | 79 | 79 | 高：步骤执行路径复杂 |
| `src/infra/benchmark_platform_adapters.py` | 855 | 263 | 92 | 中高：平台适配逻辑较重 |
| `src/workflow/patch_runner.py` | 815 | 12 | 65 | 高：补丁恢复路径复杂 |
| `src/llm/anthropic_messages_provider.py` | 810 | 15 | 63 | 中：provider 细节较多 |
| `src/workflow/runtime_evaluator.py` | 804 | 53 | 126 | 高：运行时决策逻辑集中 |
| `src/adapters/objective_ranker_adapter.py` | 792 | 1 | 90 | 中高：适配器较大 |
| `src/llm/provider_payload_parser.py` | 782 | 11 | 98 | 高：解析逻辑复杂 |
| `src/api/demo_fixtures.py` | 730 | 8 | 50 | 中：演示数据拉高 API 目录体量 |

## 4. 复杂度热点

`radon cc -n D` 的 D/E/F 级热点如下。

### 4.1 F 级热点

| 文件 | 符号 | 复杂度 | 判断 |
|---|---|---:|---|
| `src/infra/w12_vertical_experiment.py` | `aggregate_group_metrics` | F 106 | 实验指标聚合过度集中 |
| `src/infra/w12_vertical_experiment.py` | `extract_run_metrics` | F 89 | 运行指标抽取过度集中 |
| `src/storage/log_store.py` | `_extract_observability_fields` | F 71 | 日志字段抽取规则过多，适合表驱动 |
| `src/models/task_intake.py` | `_validate_registry_value` | F 63 | registry 校验分支过多 |
| `src/infra/benchmark_acceptance_gate.py` | `_build_gate_checks` | F 50 | gate check 构造逻辑过度集中 |
| `src/models/task_intake.py` | `_build_rule_extraction_payload` | F 46 | 规则抽取 payload 构造职责过多 |
| `src/workflow/plan_runner.py` | `PlanRunner.run_plan` | F 45 | 执行主循环复杂度过高 |
| `src/agents/summarizer.py` | `_render_de_novo_markdown` | F 43 | 报告渲染逻辑过度集中 |

### 4.2 E 级热点

| 文件 | 符号 | 复杂度 | 判断 |
|---|---|---:|---|
| `src/agents/executor.py` | `ExecutorAgent.refine_sequences_from_s3` | E 39 | 执行器子流程复杂 |
| `src/workflow/action_features.py` | `derive_action_features` | E 38 | 特征派生规则适合表驱动 |
| `src/workflow/recovery.py` | `select_workflow_action` | E 37 | 恢复决策核心，不能随意压缩 |
| `src/api/main.py` | `_build_tool_display` | E 37 | API 展示 DTO 构造复杂 |
| `src/infra/tool_readiness.py` | `build_capability_readiness_matrix` | E 35 | readiness 矩阵构造复杂 |
| `src/workflow/patch_runner.py` | `_extract_recovery_metadata` | E 34 | recovery 元数据抽取规则集中 |
| `src/infra/tool_readiness.py` | `_build_effective_capability_readiness_snapshot` | E 32 | readiness 快照构造复杂 |
| `src/workflow/plan_runner.py` | `_build_step_trace_data` | E 31 | trace 数据构造复杂 |
| `src/workflow/pending_action.py` | `enter_waiting_state` | E 31 | WAITING 状态进入逻辑复杂，需谨慎 |

### 4.3 D 级核心热点

| 文件 | 符号 | 复杂度 | 判断 |
|---|---|---:|---|
| `src/cli.py` | `_print_pending` | D 30 | CLI 展示逻辑可拆 |
| `src/cli.py` | `main` | D 27 | CLI 命令分发可拆 |
| `src/llm/provider_payload_parser.py` | `_parse_reference_token` | D 26 | 解析规则集中 |
| `src/workflow/belief_state.py` | `update_runtime_state` | D 28 | 运行时状态更新复杂，需测试保护 |
| `src/workflow/patch_runner.py` | `PatchRunner.run_step_with_patch` | D 27 | patch 执行流程复杂 |
| `src/models/validation.py` | `validate_plan_executability` | D 24 | plan 校验规则集中 |
| `src/agents/planner.py` | `PlannerAgent.plan_with_status` | D 24 | planner 入口职责偏重 |
| `src/infra/external_baseline_experiment.py` | 多个 run/evaluate 函数 | D 21-24 | 实验流程脚本复杂 |
| `src/infra/thesis_experiment_matrix.py` | 多个 run/matrix 函数 | D 21-23 | 实验矩阵逻辑复杂 |

## 5. 可维护性指数热点

`radon mi -n C` 报告以下文件处于 C 级可维护性区间：

| 文件 | MI | 判断 |
|---|---:|---|
| `src/agents/planner.py` | C 0.00 | 极高风险，文件过大且职责密集 |
| `src/models/task_intake.py` | C 0.00 | 极高风险，复杂校验和抽取混合 |
| `src/api/main.py` | C 0.00 | 高风险，API 聚合层过重 |
| `src/agents/executor.py` | C 0.00 | 高风险，执行逻辑复杂 |
| `src/infra/external_baseline_experiment.py` | C 0.00 | 高风险，实验脚本过长 |
| `src/infra/w12_vertical_experiment.py` | C 0.00 | 极高风险，复杂度异常集中 |
| `src/infra/thesis_experiment_matrix.py` | C 0.00 | 高风险，实验矩阵过重 |
| `src/infra/tool_readiness.py` | C 0.00 | 高风险，规则矩阵复杂 |
| `src/models/contracts.py` | C 0.00 | 中风险，契约层大但不宜轻易改 |
| `src/adapters/foldseek_adapter.py` | C 0.00 | 中高风险，适配器单体较大 |
| `src/adapters/objective_ranker_adapter.py` | C 0.00 | 中高风险，适配器单体较大 |
| `src/models/validation.py` | C 1.52 | 高风险，验证规则集中 |
| `src/llm/provider_payload_parser.py` | C 3.12 | 高风险，解析规则复杂 |
| `src/workflow/recovery.py` | C 4.67 | 极高风险，核心恢复决策复杂 |
| `src/adapters/openfold_adapter.py` | C 5.12 | 中高风险，远程/本地路径混合 |
| `src/workflow/plan_runner.py` | C 7.12 | 极高风险，FSM 主执行路径复杂 |
| `src/agents/summarizer.py` | C 8.17 | 中高风险，渲染逻辑复杂 |

说明：多个文件 MI 为 `0.00`，不应理解为“代码不可用”，而应理解为 radon 对大文件、低注释比例、高复杂度组合给出的强警告信号。

## 6. 模块级风险判断

### 6.1 极高优先级

#### `src/agents/planner.py`

- 规模：4711 code 行，最大单文件。
- 复杂度：`PlannerAgent.plan_with_status` 为 D 24，另有大量 C 级辅助函数。
- 风险：Planner 同时承载 prompt/payload 构造、候选计划生成、fallback、rerank、占位符解析、de novo 计划构造等职责。
- 建议：保持 `PlannerAgent` 作为门面，把内部逻辑拆到 `planner_payloads.py`、`planner_projection.py`、`planner_selection.py`、`planner_denovo.py` 等小模块。

#### `src/models/task_intake.py`

- 规模：2160 code 行。
- 复杂度：`_validate_registry_value` F 63，`_build_rule_extraction_payload` F 46。
- 风险：输入 schema、LLM 抽取 payload、registry 校验、安全前置检查混合在一个模型模块中。
- 建议：拆分为 intake schema、payload builder、registry validator、safety precheck 四个边界；字段语义不能改。

#### `src/workflow/plan_runner.py`

- 规模：1032 code 行。
- 复杂度：`PlanRunner.run_plan` F 45，`_build_step_trace_data` E 31。
- 风险：FSM 主执行路径和 trace 构造复杂度高。
- 建议：重构时只能拆内部纯函数和 trace builder，不能改变状态迁移、WAITING 语义、失败恢复顺序。

#### `src/workflow/recovery.py`

- 规模：1038 code 行。
- 复杂度：`select_workflow_action` E 37。
- 风险：恢复决策属于系统契约核心，压缩风险高。
- 建议：优先增加针对 action selection 的表驱动测试，再考虑把 predicate、scoring、event replay 拆出。

### 6.2 高优先级

#### `src/agents/executor.py`

- 规模：1422 code 行。
- 复杂度：`ExecutorAgent.refine_sequences_from_s3` E 39。
- 风险：执行器中的具体任务路径和通用执行责任混合。
- 建议：把 S1/S2/S3 等具体蛋白任务 helper 下沉到专用模块，保留 Executor 只负责执行边界和工具调用。

#### `src/api/main.py`

- 规模：1737 code 行。
- 复杂度：`_build_tool_display` E 37。
- 风险：API 路由、展示 DTO、pending action 详情、event filter 混合。
- 建议：拆出 `api/view_models.py`、`api/event_filters.py`、`api/pending_views.py`，减少主入口文件体量。

#### `src/storage/log_store.py`

- 规模：523 code 行。
- 复杂度：`_extract_observability_fields` F 71。
- 风险：观测字段抽取明显是规则堆积。
- 建议：改为 declarative extractor 表或小型策略函数列表。

#### `src/workflow/action_features.py`

- 规模：442 code 行。
- 复杂度：`derive_action_features` E 38。
- 风险：action 特征规则集中在单函数。
- 建议：改为 feature rule registry，但不要改变 feature 名称和含义。

#### `src/workflow/pending_action.py`

- 规模：308 code 行。
- 复杂度：`enter_waiting_state` E 31。
- 风险：WAITING 状态涉及 human decision boundary，不能靠推断重写。
- 建议：仅拆分验证、snapshot/log、state transition 三段；任何语义改动需先对照设计文档。

### 6.3 实验/验证代码高体量

`src/infra` 是后端体量的重要来源：

- `src/infra/w12_vertical_experiment.py`
- `src/infra/external_baseline_experiment.py`
- `src/infra/thesis_experiment_matrix.py`
- `src/infra/tool_readiness.py`
- `src/infra/benchmark_acceptance_gate.py`

这些文件对毕业设计验证有价值，但不应与核心 runtime 叙事混为一谈。

建议：

- 论文中归类为“实验与评估支撑代码”。
- 工程上可迁移到 `src/infra/experiments/` 或 `scripts/experiments/`。
- 优先拆分超复杂统计函数，例如 `aggregate_group_metrics`、`extract_run_metrics`、`_build_gate_checks`。

## 7. 是否存在“大规模、难以维护”的模块

结论：存在。

最明显的模块包括：

1. `src/agents/planner.py`
   - 最大单文件。
   - 职责跨度最大。
   - 是毕业设计核心机制之一，当前可解释成本偏高。

2. `src/models/task_intake.py`
   - 单文件超过 2000 code 行。
   - 有两个 F 级复杂度函数。
   - 既是契约边界又包含大量流程逻辑，维护风险高。

3. `src/workflow/plan_runner.py` / `src/workflow/recovery.py`
   - 属于 FSM 和恢复核心。
   - 复杂度高，但不能机械压缩。
   - 需要测试和设计文档保护下的结构性拆分。

4. `src/infra/w12_vertical_experiment.py`
   - 不是核心 runtime，但复杂度最高。
   - `aggregate_group_metrics` F 106，`extract_run_metrics` F 89。
   - 适合优先拆分，因为风险主要集中在实验统计正确性，不直接改变系统运行语义。

5. `src/storage/log_store.py`
   - 单文件不算最大，但存在 F 71 的观测字段抽取函数。
   - 是典型的规则堆积，应优先改成表驱动结构。

## 8. 重构与压缩建议

### 第一阶段：低风险压缩叙事，不改核心行为

目标：让毕业设计叙事从“大量后端代码”转为“核心机制 + 实验支撑”。

建议动作：

- 把 `src/infra` 中实验文件在论文中单独列为实验支撑，不计入核心 runtime。
- 将 `src/api/demo_fixtures.py` 归类为演示数据，不作为后端核心。
- 在 README 或论文工程章节中明确三层结构：
  - 核心控制层：`agents`、`workflow`、`models`。
  - 工具执行层：`adapters`、`engines`、`services`。
  - 实验验证层：`infra`、`scripts`、`reports`。

### 第二阶段：优先拆分非契约型大函数

优先级：

1. `src/infra/w12_vertical_experiment.py`
   - 拆 `aggregate_group_metrics`
   - 拆 `extract_run_metrics`

2. `src/storage/log_store.py`
   - 拆 `_extract_observability_fields`
   - 改为字段 extractor 表

3. `src/api/main.py`
   - 拆展示 DTO 构造
   - 拆 event filter
   - 拆 pending action view builder

4. `src/agents/summarizer.py`
   - 拆 `_render_de_novo_markdown`
   - 把 markdown section builder 独立为小函数

这些改动对核心 FSM/agent 契约影响较小，适合作为首轮重构。

### 第三阶段：谨慎拆分核心机制模块

这些模块可以拆，但不能改语义：

- `src/agents/planner.py`
- `src/models/task_intake.py`
- `src/workflow/plan_runner.py`
- `src/workflow/recovery.py`
- `src/workflow/pending_action.py`

要求：

- 重构前用 doc-slicer 检索相关设计片段。
- 只做职责拆分和纯函数迁移。
- 不改 FSM 状态、transition、WAITING 语义、replan/patch/retry 顺序。
- 每次拆分都配套 focused tests。

## 9. 建议的毕业设计表述

不建议在论文里强调“后端 4.5 万行代码”。更合适的表述是：

- 核心系统实现由多智能体控制层、显式 FSM 工作流层、工具适配层、运行时观测层组成。
- 实验与验证支撑代码单独维护，用于批量实验、指标聚合、benchmark 和可视化报告生成。
- 当前代码规模较大，因此后续工程优化重点是降低核心模块复杂度，而不是继续扩展功能。

## 10. 总体优先级

| 优先级 | 模块 | 原因 | 建议 |
|---|---|---|---|
| P0 | `src/infra/w12_vertical_experiment.py` | 最高复杂度，非核心语义 | 先拆统计函数 |
| P0 | `src/storage/log_store.py` | F 71，规则堆积 | 表驱动 extractor |
| P1 | `src/api/main.py` | API 入口过重 | 拆 view/filter builder |
| P1 | `src/agents/planner.py` | 最大核心模块 | 保持 facade，拆内部职责 |
| P1 | `src/models/task_intake.py` | F 级校验/抽取 | 拆 validator/payload/precheck |
| P2 | `src/workflow/plan_runner.py` | FSM 主路径复杂 | 测试保护下拆 trace/run helpers |
| P2 | `src/workflow/recovery.py` | 恢复决策复杂 | 测试保护下拆 predicates/scoring |
| P2 | `src/agents/executor.py` | 任务子流程复杂 | 拆具体 protein task helpers |

## 11. 最终判断

可以进行一定程度重构和压缩，但不建议以删行为主要目标。

合理目标：

- 第一轮：通过分层叙事和移动实验支撑代码，把“核心后端”口径从整体后端中收束出来。
- 第二轮：拆分高复杂度非契约模块，降低 radon F/E 热点数量。
- 第三轮：在测试和设计文档保护下拆分 `planner`、`task_intake`、`workflow` 核心模块。

不合理目标：

- 为了让代码行数看起来少而合并、删除或弱化公共契约。
- 在没有设计文档确认的情况下改 FSM、recovery、human confirmation、agent role boundary。
- 把核心复杂度藏到更抽象但不可读的动态配置里。

当前最值得做的不是“大规模瘦身”，而是“把复杂度从少数巨型函数和巨型文件中释放出来”。
