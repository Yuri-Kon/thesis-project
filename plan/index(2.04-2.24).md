# Week 7-9(2.04-2.24)规划

> Precondtion:
> - Week6 关键任务未完成（Demo 启动脚本 / 状态页 / HITL 决策页 / 日志视图 / Demo 文档）
> - 现有系统已具备 FSM/HITL 与最小可运行 Demo 基础
> - ProteinToolKG 已作为 Planner 的唯一工具事实来源

## Week 7(02.04-02.10)

### 主题：Week6 遗留收敛 + Demo 可用化

### 核心目标

- 解决 Week6 未完成项，保证 Demo 可启动、可理解、可演示
- 给评审一个“从入口到结果”的可视化路径

### 本周 Issue 列表

- W7-01 Demo 启动脚本与最小配置
- W7-02 任务状态页（FSM 可视化）
- W7-03 HITL 决策页（PendingAction 提交）
- W7-04 运行日志视图（EventLog 时间线）
- W7-05 Demo 使用说明与演示流程

### 关键 Issue 设计

|模块|Issue|具体工作内容|验收标准|追溯点|
|:---|:----|:-----------|:-------|:-----|
|Infra|W7-01 Demo 启动脚本与最小配置|统一入口脚本（如 `run_demo.sh`）串起 API/Worker/示例任务；补齐 demo 配置（端口/数据目录/模型开关）；失败时打印可定位日志|新环境执行脚本后 10 分钟内可启动 Demo 并进入可访问的 API/UI|`run_demo.sh`，`scripts/`，`configs/`，`docs/demo/README.md`|
|Frontend|W7-02 任务状态页（FSM 可视化）|实现任务列表与单任务状态详情（state/step_index/plan_version）；展示 WAITING_* 明确提示；与现有 API 对接|给定 task_id 可在页面看到当前 FSM 状态与关键字段|`src/api/`，`docs/demo/`（UI 说明与资产），`examples/`（UI 原型）|
|Frontend|W7-03 HITL 决策页（PendingAction 提交）|展示 pending_action.candidates 与风险/成本摘要；提供 approve/reject/选择候选；调用 decision 提交接口|能通过 UI 提交决策并推动状态从 WAITING_* 到 PLANNED/RUNNING|`src/api/`，`docs/demo/`，`examples/`|
|Observability|W7-04 运行日志视图（EventLog 时间线）|新增/完善事件查询 API；前端展示时间线与关键事件节点（WAITING_*、DECISION_APPLIED、STEP_DONE）|UI 可看到按时间排序的 EventLog 且字段完整|`src/infra/`，`src/api/`，`docs/demo/`|
|Docs|W7-05 Demo 使用说明与演示流程|补充“从启动到 HITL 决策”的完整操作步骤；列出环境依赖与常见问题；提供截图|评审按照文档可复现 Demo|`docs/demo/README.md`|

### Issue 具体工作内容（列表补充）

- W7-01：补齐 demo 配置文件与一键启动脚本，确保失败时有可定位日志与下一步提示
- W7-02：实现任务列表与状态详情页，突出 WAITING_* 状态与关键字段
- W7-03：实现 PendingAction 详情展示与决策提交表单
- W7-04：实现 EventLog 时间线视图与关键事件筛选
- W7-05：完善 Demo 文档与演示流程（含依赖、步骤、截图）

### Week 7 可交付物

- 可一键启动的 Demo（含最小配置）
- 可视化状态页 + HITL 决策页 + 日志时间线
- 完整可复现的 Demo 文档

---

## Week 8(02.11-02.17)

### 主题：新工具接入 + KG 扩展（AlphaFold 作为高精度预测路径）

### 核心目标

- ProteinToolKG 增加 AlphaFold，并可被 Planner 合理选择
- 形成 “ESMFold/AlphaFold 可切换” 的预测闭环

### 本周 Issue 列表

- W8-01 ProteinToolKG 扩展：AlphaFold 节点与约束
- W8-02 AlphaFoldAdapter（远程调用与结果标准化）
- W8-03 Planner 选择策略与解释（基于 KG 约束）
- W8-04 AlphaFold 端到端最小测试
- W8-05 文档与 Demo 入口更新

### 关键 Issue 设计

|模块|Issue|具体工作内容|验收标准|追溯点|
|:---|:----|:-----------|:-------|:-----|
|KG|W8-01 ProteinToolKG 扩展：AlphaFold 节点与约束|补充 AlphaFold tool/IOType/Capability/Constraint（如 GPU/远程/耗时）；标注版本与 cost 维度；同步示例|Planner 可检索到 AlphaFold，并能基于约束过滤|`src/kg/`，`docs/design/`（KG 说明）|
|Tool|W8-02 AlphaFoldAdapter（远程调用与结果标准化）|基于 RemoteModelInvocationService 实现 submit/poll/download；输出标准化 StepResult 与 artifacts 映射；失败码归一化|AlphaFold StepResult 字段齐全且可被 Summarizer 消费|`src/tools/`，`src/adapters/`，`src/infra/`|
|Planner|W8-03 Planner 选择策略与解释（基于 KG 约束）|新增选择策略：当 task.constraints 需要高精度时优先 AlphaFold；解释信息引用 KG 事实（版本/成本/限制）|同一任务可通过配置切换 ESMFold/AlphaFold，plan 合法且解释可读|`src/agents/`，`src/kg/`|
|Executor|W8-04 AlphaFold 端到端最小测试|增加最小集成测试（可 mock 远程调用）；验证执行链路与 artifacts 贯通|测试通过且可在 CI/本地复现|`tests/`，`examples/`|
|Docs|W8-05 文档与 Demo 入口更新|更新 Demo 文档与配置说明，明确选择 ESMFold/AlphaFold 的入口|文档明确可按步骤选择预测工具|`docs/demo/README.md`，`configs/`|

### Issue 具体工作内容（列表补充）

- W8-01：在 KG 中新增 AlphaFold 节点与约束，并更新示例与说明
- W8-02：实现 AlphaFoldAdapter 远程调用与结果落地，统一 StepResult
- W8-03：调整 Planner 选择逻辑与解释模板，使工具选择可审计
- W8-04：补充端到端最小测试，覆盖 AlphaFold 执行与 artifacts 贯通
- W8-05：更新 Demo 文档与配置，明确切换预测工具的入口

### Week 8 可交付物

- AlphaFold 工具链已可规划与执行
- Planner 解释可说明工具选择依据
- 端到端最小测试与文档更新

---

## Week 9(02.18-02.24)

### 主题：稳定性/复现性 + 执行后端抽象

### 核心目标

- 固化可复现 Demo（版本/配置/产物可追踪）
- 为 Nextflow 等后端预留清晰执行抽象

### 本周 Issue 列表

- W9-01 ExecutionBackend 抽象与默认实现
- W9-02 可复现配置与运行清单
- W9-03 结构评估/评分最小工具接入
- W9-04 报告与版本追踪增强

### 关键 Issue 设计

|模块|Issue|具体工作内容|验收标准|追溯点|
|:---|:----|:-----------|:-------|:-----|
|Engines|W9-01 ExecutionBackend 抽象与默认实现|抽象 LocalBackend/RemoteBackend 接口；Executor 通过 backend 执行；预留 NextflowBackend 空实现与配置入口|不改变现有 Demo 行为；可通过配置切换 backend|`src/engines/`，`src/workflow/`，`configs/`|
|Infra|W9-02 可复现配置与运行清单|补充 demo 配置锁定（模型版本/随机种子/输入样例）；输出运行清单（versions + config）|相同配置可复现相同流程与关键指标|`configs/`，`docs/impl/`，`output/`|
|Tool|W9-03 结构评估/评分最小工具接入|接入轻量评估（如 pLDDT 统计或 FoldX/FastScore 占位）；写入 StepResult.metrics；KG 增加评分工具节点|Plan 可包含评估步骤并生成可用评分|`src/tools/`，`src/kg/`，`tests/`|
|Summarizer|W9-04 报告与版本追踪增强|报告中增加工具版本、模型版本、配置摘要、评估指标；对齐可审计口径|Summarizer 输出可追溯到配置与版本|`src/agents/`，`docs/demo/`|

### Issue 具体工作内容（列表补充）

- W9-01：抽象执行后端接口并提供默认实现，预留 NextflowBackend
- W9-02：锁定 demo 配置与版本清单，输出可复现实验清单
- W9-03：增加最小结构评估步骤与评分指标，写入 StepResult.metrics
- W9-04：增强报告信息，确保版本与配置可追溯

### Week 9 可交付物

- ExecutionBackend 抽象完成且不破坏现有流程
- Demo 可复现（配置锁定 + 版本清单 + 评分结果）
- 总结报告可追溯到配置与版本

---

## 可追溯性约定

- 每个 Issue 必须关联至少一个代码/文档位置与一个验收产物
- 代码追溯：`src/`、`tests/`、`configs/`、`docs/` 对应修改路径
- 产物追溯：Demo 结果与运行清单保存在 `output/` 或演示指定目录
