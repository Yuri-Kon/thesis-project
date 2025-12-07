# 进度规划 2025-12-08 

## 进度明细

### 已完成内容(截至12.08)

| 模块                    | 工作内容                                                                                                        | 完成情况 | 备注                                  |
| --------------------- | ----------------------------------------------------------------------------------------------------------- | ---- | ----------------------------------- |
| 数据契约 Models           | ProteinDesignTask, Plan, PlanStep, StepResult, SafetyResult, DesignResult, WorkflowContext, Replan/Patch 契约 | ✔ 完成 | 字段、类型完全对齐设计文档                       |
| 时间戳工具                 | now_iso() 修复弃用 utcnow                                                                                       | ✔ 完成 | 使用 timezone-aware 时间 ISO8601        |
| 任务状态机                 | TaskStatus（CREATED → DONE，全 FSM）                                                                            | ✔ 完成 | 与 system-implementation-design 完全一致 |
| TaskRecord/StepRecord | 全局任务记录结构                                                                                                    | ✔ 完成 | 为 API/DB 提供统一结构                     |
| Agent 框架（接口）          | Planner / Executor / Safety / Summarizer 接口定义                                                               | ✔ 完成 | 后续将补充真实逻辑                           |
| Agent 最小实现            | Planner（dummy 计划）、Executor（dummy 执行）、Summarizer（dummy 汇总）                                                   | ✔ 完成 | 可完整跑通 demo                          |
| workflow              | run_task_sync 串联所有 Agent                                                                                    | ✔ 完成 | 可生成 DesignResult + 文件报表             |
| TaskAPI               | POST /tasks, GET /tasks/{task_id}                                                                           | ✔ 完成 | 可通过 Swagger UI 调试                   |
| 最小Demo                | 成功执行任务、生成报告文件                                                                                               | ✔ 完成 | 项目首次可执行的 pipeline                   |

---

## 后续阶段计划(12.09之后)

以下是未来三周的任务安排

### Week 3（12.09 – 12.15）—— Adapter 层 & 工具知识图谱（KG）建设

| 日期        | 目标模块                | 详细任务内容                                                                  | 预期产出                   | 备注                        |
| --------- | ------------------- | ----------------------------------------------------------------------- | ---------------------- | ------------------------- |
| **12.09** | Adapter 基类          | 定义 `BaseToolAdapter` 接口：`resolve_inputs`、`run_local`、`run_container`    | `src/adapters/base.py` | 作为所有工具适配器父类               |
| **12.10** | Adapter 注册机制        | 实现 `ADAPTER_REGISTRY`（工具发现机制），提供 `register_adapter()` & `get_adapter()` | 适配器注册系统完成              | Planner / Executor 用它查找工具 |
| **12.11** | ESMFoldAdapter Mock | 实现 `esmfold_adapter.py`（mock）：输出假 pdb / 假 metrics                       | 可运行的 mock 工具           | 可在 Demo 中替换 dummy tool    |
| **12.12** | ProteinToolKG       | 编写 `protein_tool_kg.json`（包含 esmfold / mpnn / rfdiffusion 模型描述）         | 完整工具知识图谱               | Adapter 层和 Planner 均依赖    |
| **12.13** | KGClient            | 实现 `kg_client.py`：加载 KG、按 capability 查询工具                               | KG 查询接口完成              | Planner 可根据 KG 选择工具       |
| **12.14** | Executor v2         | 将 Executor 修改为“通过 Adapter 调用工具”而不是 dummy execution                      | 真正框架化执行                | run_local 执行 mock ESMFold |
| **12.15** | Demo v2 测试          | E2E 测试：“任务 → Planner → Adapter → Executor → Summarizer”                 | Demo v2（真正工具调用链）       | 可汇报给导师（12月中旬版本）           |

### Week 4（12.16 – 12.22）—— Planner v2、多步骤 Plan、SafetyAgent

| 日期        | 目标模块                 | 详细任务内容                                               | 预期产出                        |
| --------- | -------------------- | ---------------------------------------------------- | --------------------------- |
| **12.16** | Planner v2           | Planner 改为从 KG 自动选择工具（capabilities 匹配）               | 最小智能规划器                     |
| **12.17** | 多步骤支持                | 支持生成包含多个步骤的 Plan（示例：序列生成 → 结构预测 → 评估）                | Plan v2                     |
| **12.18** | 输入引用机制               | 实现 PlanStep 输入引用：`"S1.sequence"` → 自动从 StepResult 取值 | Executor + Adapter 支持动态输入引用 |
| **12.19** | SafetyAgent 初版       | 实现 S1/S2 安全检查（输入/输出检查）                               | 蛋白质设计安全层                    |
| **12.20** | 整合 Safety → Executor | Executor 在每次 run_step 前后调用 SafetyAgent               | 完整安全机制接入                    |
| **12.21** | TaskAPI 扩展           | GET /tasks/{id} 输出 step_summary（含 metrics、risk、工具信息） | API 更适合导师展示                 |
| **12.22** | Demo v3 测试           | 运行多步骤 pipeline（如：MPNN → ESMFold → RDKit props）       | Demo v3（增强版）                |

### Week 5（12.23 – 12.29）—— 接入真实工具、Nextflow、日志与稳定性

| 日期        | 模块                   | 详细工作内容                                       | 产出                |
| --------- | -------------------- | -------------------------------------------- | ----------------- |
| **12.23** | ESMFold 实例化          | 实现 ESMFoldAdapter 真正的本地推理（或容器推理）版本           | 结构预测可真实执行         |
| **12.24** | ProteinMPNN Adapter  | 序列设计工具适配器（本地 / 容器）                           | 具备完整序列→结构能力       |
| **12.25** | RFdiffusion Adapter  | 第一个复杂工具（可先做 mock，然后接容器）                      | 可插拔复杂 pipeline 工具 |
| **12.26** | NextflowAdapter      | 编写 NextflowAdapter：Executor 可以调用 NF pipeline | 与真正生信 Pipeline 对接 |
| **12.27** | FileStore & LogStore | 统一文件输出（pdb、json、metrics）、日志目录结构              | 后续论文截图素材          |
| **12.28** | 性能优化与错误处理            | 处理工具调用失败、重试策略、错误日志                           | 系统稳定性提升           |
| **12.29** | Demo v4（真实工具版）       | 运行一个“真实设计任务”的完整 pipeline                     | 可作为中期检查视频/demo    |
