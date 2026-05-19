# 结题验收 5 分钟现场演示讲稿

日期：2026-05-20

适用场景：结题验收现场演示。本文按 5 分钟设计，精确到每一步打开哪个页面、做什么操作、说什么说明。

## 0. 上台前准备

上台前先启动服务，不把启动时间算入 5 分钟演示。

```bash
PROTEIN_ENABLE_DEMO_FIXTURES=1 \
UV_CACHE_DIR=/tmp/uv-cache \
uv run python scripts/run_demo.py --port 8000 --no-smoke-test
```

另开终端注入答辩演示数据：

```bash
curl -X POST http://127.0.0.1:8000/demo/defense-full-flow
```

浏览器提前打开 5 个标签页：

```text
http://127.0.0.1:8000/ui
http://127.0.0.1:8000/ui/task-builder
http://127.0.0.1:8000/ui/tasks/demo_defense_hitl
http://127.0.0.1:8000/ui/tasks/demo_defense_done
http://127.0.0.1:8000/ui/tasks/demo_defense_done/events
```

## 1. 0:00 - 0:35 开场：系统定位

操作：打开 `/ui` Dashboard。

讲稿：

```text
各位老师好，我现在演示的是论文中的蛋白质设计多 Agent 工作流系统。这个系统不是单次调用一个大模型，而是把蛋白质设计任务组织成可规划、可执行、可恢复、可审计的工作流。

论文第四章中，我把系统分成任务接入、规划、执行、安全审查、结果汇总和工具资源层。这里 Dashboard 展示的是任务入口和任务状态，后续我会沿着一条固定演示链路展示输入、HITL 决策、执行结果、结构查看和事件审计。

现场演示使用本地确定性 demo fixture，不调用远程 LLM 或 OpenFold3 服务，目的是稳定展示系统机制。真实实验结果在论文第七章和冻结实验产物中说明。
```

## 2. 0:35 - 1:15 输入解析与任务录入

操作：切到 `/ui/task-builder`。

讲稿：

```text
这里是任务录入页面。系统入口支持自然语言任务描述，并进一步收敛到结构化任务字段。

本次演示任务是：评估一个 TRP-cage-like 短肽序列的稳定性，优先采用低成本结构预测路径，并在高代价步骤前展示候选方案给人工确认。
```

如果页面上有字段，指着字段继续说：

```text
可以看到任务会被整理为 sequence、objective type、budget policy、runtime policy、是否需要人工审查等字段。这样做的原因是，后续 PlannerAgent 不能只根据一句自然语言直接执行，而是要基于明确约束生成候选计划。

这对应论文第三章的任务接入需求，以及第四章中“目标、约束、工具能力和预算共同决定候选工作流”的设计。
```

## 3. 1:15 - 2:45 HITL 候选比较与算法解释

操作：切到 `/ui/tasks/demo_defense_hitl`。先停留在 pending action / candidate comparison 区域，再依次指向候选评分、运行状态 JSON 和右侧“理论对象”面板。

讲稿：

```text
现在这个任务处于 WAITING_PATCH_CONFIRM 状态。这个状态是有限状态机中的等待态，含义是系统已经暂停执行，正在等待人工确认。

这里展示的是一个高代价步骤前的 patch 确认场景：远程结构预测服务 readiness 降级，系统没有继续盲目执行，而是生成了三个候选方案。
```

指向三个候选，说：

```text
第一个 patch_local_openfold 是默认推荐，风险低、成本低，分数最高。

第二个 suffix_replan_low_cost 是保留已完成前缀，改用低成本后缀重规划。

第三个 patch_remote_retry 是继续重试远程服务，但成本和风险更高。

这里的重点不是让 AI 自动替我批准，而是系统给出候选、分数、风险、成本和解释，由人来做最终决策。
```

### 3.1 解释候选评分 JSON

操作：指向候选卡片中的 score breakdown。如果页面展示 JSON 或可展开详情，就展开评分字段。

页面中的评分 JSON：

```json
{
  "feasibility": 0.88,
  "objective": 0.82,
  "risk": 0.9,
  "cost": 0.86,
  "overall": 0.86
}
```

讲稿：

```text
这里的评分对应论文第四章 CEBRA-WP 的静态效用部分。feasibility 表示这个候选在工具能力、输入输出契约和前后步骤衔接上是否可执行；objective 表示它和当前稳定性评估目标的匹配程度；risk 表示风险越低分越高；cost 表示成本越低分越高；overall 是综合分。

所以这个 0.86 不是大模型随口给出的分数，而是把可行性、目标匹配、风险和成本拆开之后再合成的候选效用。这样做的好处是，老师或者用户可以追问“为什么推荐它”，系统能够把依据拆开解释。
```

### 3.2 解释运行状态 JSON

操作：指向运行状态 / runtime state 区域。如果页面展示 JSON，就停留 5 到 8 秒。

页面中的运行状态 JSON：

```json
{
  "schema_version": 1,
  "p_success": 0.64,
  "p_structural_failure": 0.31,
  "recovery_margin": 0.72,
  "expected_remaining_cost": 1.35,
  "evidence_sufficiency": 0.58,
  "budget_pressure": 1.12,
  "budget_cap": 1.2
}
```

讲稿：

```text
这里是 Lite belief-state，也就是论文里说的轻量信念状态。它不是完整 POMDP，也不是强化学习控制器，而是一个可解释的运行时状态向量。

p_success 为 0.64，表示在当前观测下继续恢复执行的成功倾向是中等偏高；p_structural_failure 为 0.31，说明结构相关失败风险并不为零，所以不能直接忽略。

recovery_margin 为 0.72，表示已完成前缀还有保留价值，适合优先做局部 patch，而不是直接全量重规划。expected_remaining_cost 为 1.35，说明后面还有一定成本暴露。

evidence_sufficiency 为 0.58，说明证据不是完全充分；budget_pressure 为 1.12，接近 budget_cap 1.2，说明预算压力已经比较明显。因此系统选择进入 WAITING_PATCH_CONFIRM，让人确认是否采用低成本 patch。
```

算法收束：

```text
从算法角度看，这一步就是 CEBRA-WP 的运行时自适应层：系统先根据 StepResult、tool readiness 和历史执行结果更新 runtime state，再用这个状态解释为什么此时不直接继续高代价远程调用，而是生成 patch_confirm 的 PendingAction。
```

### 3.3 解释右侧“理论对象”面板

操作：指向右侧“理论对象”面板，按从上到下的顺序解释。

讲稿：

```text
右侧这个“理论对象”面板是把论文里的算法变量映射到页面上。

静态分 0.86 对应候选在运行时观测介入前的先验效用，也就是由 feasibility、objective、risk 和 cost 得到的分数。

运行时调整这里显示为横线，表示这个 demo 卡片没有额外展示单独的 delta 标量；运行时状态单独展示在前面的 JSON 中。最终分 0.86 表示当前用于排序和推荐的候选效用。

选中操作是补丁确认，说明算法不是直接执行 patch，而是把 patch 作为候选动作提交给 HITL。证据充分性 0.58 和预算压力 1.12 分别对应 Lite belief-state 中的 evidence_sufficiency 和 budget_pressure，它们共同解释为什么这里需要人工确认。
```

再用一句话靠近公式：

```text
如果用论文里的形式表达，这里就是对候选 pi 先计算静态效用 S_static(pi)，再结合运行时状态 x_t 形成运行时效用 U(pi, x_t)，最后把推荐动作映射到 FSM 的 WAITING_PATCH_CONFIRM 状态。算法可以给建议，但状态推进和人工确认仍由 FSM 和 HITL 契约控制。
```

## 4. 2:45 - 3:25 完成态结果与报告

操作：切到 `/ui/tasks/demo_defense_done`。先展示状态、报告、scores。

讲稿：

```text
这里展示的是同一条链路在人工接受推荐 patch 后的完成态。任务状态已经进入 DONE。

结果中包含序列、结构文件、评分、风险标记和报告路径。这里的报告不是单纯一段自然语言总结，而是把 objective scoring、structure similarity、证据来源和 warning 一起保存下来。
```

指向 warning 或 source 字段，说：

```text
可以看到 demo artifact 明确标记为本地演示产物，不把它包装成真实远程模型推理结果。这一点和论文中的边界一致：本文验证的是工作流机制、恢复控制和审计能力，不宣称通过现场演示证明蛋白质真实生物学功能。
```

## 5. 3:25 - 3:55 三维结构查看

操作：在同一个任务详情页中找到 Structure Viewer。旋转、缩放一次，点击或悬停结构。

讲稿：

```text
这里是结构查看器，系统可以直接加载任务产出的 PDB 文件，并在前端展示三维结构。

在真实使用中，这个位置可以接入 ESMFold、OpenFold3 或其他结构预测工具的输出。现场演示使用固定 PDB，是为了保证答辩时页面稳定。系统关心的是结构产物能否被记录、展示、评分和追溯。
```

解释模块划分：

```text
从模块上看，结构文件由工具适配层或 demo fixture 产生，后端 API 提供结构接口，前端 Task Detail 负责展示；工作流状态仍由 src/workflow 维护，不由前端直接改状态。
```

## 6. 3:55 - 4:35 事件时间线与审计

操作：切到 `/ui/tasks/demo_defense_done/events`。

讲稿：

```text
最后看事件时间线。这里记录了从任务创建、规划、运行、工具 readiness 降级、runtime state 更新、创建 pending action、进入等待态、提交决策、应用决策、退出等待态，到最终总结和 DONE 的完整链路。

这对应论文中 EventLog 和 TaskSnapshot 的设计。它的价值是：系统不是黑箱地给出一个结果，而是可以回放“为什么停下来、为什么推荐这个候选、谁做了决策、之后状态如何变化”。
```

指向 `WAITING_ENTER`、`DECISION_APPLIED`、`WAITING_EXIT`、`DONE`：

```text
这几个事件体现了 HITL 的关键边界：进入等待态后执行暂停，人工决策写入后才继续推进，最后进入完成态。
```

## 7. 4:35 - 5:00 实验结果与收束

操作：回到 Dashboard 或停留在事件页都可以，不再切复杂页面。

讲稿：

```text
论文第七章中，我用 12 个 task key、4 组策略、共 84 次运行验证系统机制。最终 81 次 DONE、3 次 FAILED。

需要说明的是，static_top1 在当前矩阵中成功率最高，为 100%；其他三组为 95.2%。所以我没有把结论写成“CEBRA-WP 显著提高成功率”。本文更稳妥的结论是：CEBRA-WP 机制链路可执行、Lite belief-state 可观测、恢复决策可审计，并且固定阈值门控会带来额外高代价调用。

总结来说，这个系统的核心贡献是把 LLM Agent、工具知识、FSM、HITL、运行时恢复和审计日志组织成一个可复现的蛋白质设计工作流原型。
```

## 8. 老师打断时的短答

### 问：这是实时跑模型吗？

```text
不是。现场为了稳定性使用本地确定性 fixture，不调用远程 LLM、PLM REST 或 OpenFold3 REST。它展示的是系统交互、FSM、HITL、结构查看和审计链路。真实实验结果来自论文第七章的 84-run 冻结实验矩阵。
```

### 问：为什么不用普通固定流水线？

```text
普通固定流水线适合步骤稳定、成本均匀、失败语义简单的任务。但蛋白质设计工作流里，结构预测、精修和目标评分往往高成本，而且失败可能来自工具异常、输入质量不足或候选链路整体不可行。因此系统需要在运行时根据观测决定继续、patch、suffix replan 或 stop。
```

### 问：CEBRA-WP 的核心是什么？

```text
它是工作流层的规划与恢复控制算法，不是新的蛋白质生成模型。核心过程是：候选生成、硬可行性过滤、静态评分、运行时状态更新、候选重排序和恢复动作选择。它的目标是在高代价、会失败的科研工作流中减少盲目执行，并保留可解释的恢复路径。
```

### 问：Lite belief-state 是什么？

```text
它是一个轻量运行时状态向量，包含五个量：成功概率、结构性失败风险、恢复余量、剩余成本和证据充分性。它不是完整 POMDP 或强化学习控制器，而是为了让恢复决策可解释、可审计、可复现。
```

### 问：实验中 static_top1 成功率更高，算法价值在哪里？

```text
我没有把结论写成 CEBRA-WP 显著提高成功率。当前 84-run 矩阵支持的是机制结论：CEBRA-WP 链路可执行，Lite belief-state 可观测，HITL 和恢复决策可审计，固定阈值门控会带来额外高代价调用。算法价值主要在恢复控制、成本意识和审计解释，而不是单纯成功率提升。
```

### 问：系统缺陷是什么？

```text
主要有四点。第一，84-run 实验规模有限，统计效力不足。第二，矩阵中真实 patch 主要出现在 fixed_threshold_gate 组，suffix_replan 和 terminal_stop 的矩阵级证据还不够。第三，系统仍是原型，数据库持久化、ToolKG 动态更新和远程服务故障切换还可以加强。第四，外部 Agent 基线还可以扩展，比如 ReAct、Tree of Thoughts 和 Reflexion。
```

## 9. 如果时间只剩 3 分钟

只讲这 4 个页面：

```text
http://127.0.0.1:8000/ui/task-builder
http://127.0.0.1:8000/ui/tasks/demo_defense_hitl
http://127.0.0.1:8000/ui/tasks/demo_defense_done
http://127.0.0.1:8000/ui/tasks/demo_defense_done/events
```

压缩主线：

```text
输入结构化 -> 高代价步骤前等待人工确认 -> 候选按风险成本和 runtime state 排序 -> 接受 patch 后完成 -> 报告、结构、事件日志可追溯。
```
